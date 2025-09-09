from __future__ import annotations
import asyncio
from typing import Optional, TypeVar, Any, Generic, Callable
import uuid
import time
from .context import Context
from .core import Failure, Exit, Cause, Effect, annotate_cause
from .scope import Scope

E = TypeVar("E"); A = TypeVar("A")

class Fiber(Generic[E, A]):
    """A lightweight async task with structured cancellation.
    
    Fibers are effectpy's unit of concurrent execution. Unlike raw asyncio Tasks,
    fibers provide structured error handling and proper cancellation semantics.
    
    Args:
        task: The underlying asyncio task
        name: Optional name for debugging
        
    Attributes:
        id: Unique identifier for this fiber
        name: Optional name for debugging
        status: Current status ('running', 'done', 'failed', 'cancelled')
    """
    def __init__(self, task: asyncio.Task, name: Optional[str] = None):
        self._task = task
        self.id: str = uuid.uuid4().hex
        self.name: Optional[str] = name
        self._status: str = "running"
        # status transitions handled in done callbacks by Runtime

    @property
    def status(self) -> str:
        return self._status

    async def await_(self) -> Exit[E, A]:
        """Wait for this fiber to complete and get the structured result.
        
        Returns:
            Exit containing either the success value or failure cause
            
        Example:
            ```python
            fiber = runtime.fork(my_effect())
            exit_result = await fiber.await_()
            
            if exit_result.success:
                print(f"Success: {exit_result.value}")
            else:
                print(f"Failure: {exit_result.cause.render()}")
            ```
        """
        try:
            v = await self._task
            self._status = "done"
            return Exit(success=True, value=v)
        except Failure as fe:
            self._status = "failed"
            c = Cause.fail(fe.error)
            for n in getattr(fe, 'annotations', []) or []:
                c = annotate_cause(c, str(n))
            return Exit(success=False, cause=c)
        except asyncio.CancelledError:
            self._status = "cancelled"
            return Exit(success=False, cause=Cause.interrupt())
        except BaseException as ex:
            self._status = "failed"
            return Exit(success=False, cause=Cause.die(ex))

    async def join(self) -> A:
        """Wait for this fiber to complete and get the success value.
        
        Returns:
            The success value if the fiber succeeds
            
        Raises:
            Failure: If the fiber fails with a business logic error
            Exception: If the fiber dies with an unexpected exception
            
        Note:
            This is similar to await_() but throws exceptions instead
            of returning structured Exit values.
        """
        return await self._task

    def interrupt(self) -> None:
        """Cancel this fiber.
        
        Sends a cancellation signal to the underlying task. The fiber
        will transition to 'cancelled' status.
        
        Example:
            ```python
            fiber = runtime.fork(long_running_task())
            # Later...
            fiber.interrupt()  # Cancel the fiber
            ```
        """
        self._task.cancel()

    def inherit_refs(self) -> None:
        # ContextVars are inherited by default for new tasks in Python
        return None


class Supervisor:
    async def on_start(self, fiber: Fiber[Any, Any]) -> None:
        pass

    async def on_end(self, fiber: Fiber[Any, Any], exit_: Exit[Any, Any]) -> None:
        pass

    async def on_failure(self, fiber: Fiber[Any, Any], cause: Cause[Any]) -> None:
        pass

class Runtime:
    """Manages effect execution and fiber lifecycle.
    
    Runtime provides advanced features for concurrent execution including
    fiber management, supervision, and structured error handling.
    
    Args:
        base: Base context for all effects (default: empty Context)
        supervisor: Supervisor for fiber lifecycle callbacks (default: no-op)
        
    Example:
        ```python
        runtime = Runtime()
        
        # Fork effects as fibers
        fiber1 = runtime.fork(fetch_data("source1"))
        fiber2 = runtime.fork(fetch_data("source2"))
        
        # Wait for results
        result1 = await fiber1.join()
        result2 = await fiber2.join()
        
        await runtime.shutdown()
        ```
    """
    def __init__(self, base: Optional[Context] = None, supervisor: Optional[Supervisor] = None):
        self.base = base or Context()
        self.supervisor = supervisor or Supervisor()

    def fork(self, eff: Effect[Any, E, A], name: Optional[str] = None) -> Fiber[E, A]:
        """Fork an effect as a new fiber.
        
        The effect starts executing immediately in the background.
        
        Args:
            eff: The effect to execute
            name: Optional name for debugging
            
        Returns:
            A Fiber representing the running effect
            
        Example:
            ```python
            fiber = runtime.fork(long_running_task(), name="background-worker")
            
            # Do other work...
            
            result = await fiber.join()  # Wait for completion
            ```
        """
        async def runner():
            return await eff._run(self.base)

        task = asyncio.create_task(runner())
        fiber: Fiber[E, A] = Fiber(task, name=name)

        # Notify supervisor of start
        asyncio.create_task(self.supervisor.on_start(fiber))

        def _on_done(t: asyncio.Task):
            # Best-effort status and callbacks
            if t.cancelled():
                fiber._status = "cancelled"
                exit_ = Exit(success=False, cause=Cause.interrupt())
                asyncio.create_task(self.supervisor.on_end(fiber, exit_))
                return
            try:
                v = t.result()
                fiber._status = "done"
                exit_ = Exit(success=True, value=v)
                asyncio.create_task(self.supervisor.on_end(fiber, exit_))
            except Failure as fe:
                fiber._status = "failed"
                cause = Cause.fail(fe.error)
                exit_ = Exit(success=False, cause=cause)
                asyncio.create_task(self.supervisor.on_failure(fiber, cause))
                asyncio.create_task(self.supervisor.on_end(fiber, exit_))
            except BaseException as ex:
                fiber._status = "failed"
                cause = Cause.die(ex)
                exit_ = Exit(success=False, cause=cause)
                asyncio.create_task(self.supervisor.on_failure(fiber, cause))
                asyncio.create_task(self.supervisor.on_end(fiber, exit_))

        task.add_done_callback(_on_done)
        return fiber

    async def run(self, eff: Effect[Any, E, A]) -> A:
        return await eff._run(self.base)

    async def run_scoped(self, eff: Effect[Any, E, A], scope: Scope) -> A:
        try:
            return await eff._run(self.base)
        finally:
            await scope.close()
