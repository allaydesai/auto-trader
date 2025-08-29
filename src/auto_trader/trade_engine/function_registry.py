"""Execution function registry for plugin-based function management."""

import asyncio
from typing import Dict, List, Type, Optional, Any

from loguru import logger

from auto_trader.models.execution import ExecutionFunctionConfig
from auto_trader.trade_engine.execution_functions import ExecutionFunctionBase


class ExecutionFunctionRegistry:
    """Registry for execution function plugins.

    Manages registration, instantiation, and discovery of execution functions.
    Uses asyncio-safe synchronization patterns for concurrent access protection.
    """

    def __init__(self):
        """Initialize registry."""
        self._functions: Dict[str, Type[ExecutionFunctionBase]] = {}
        self._instances: Dict[str, ExecutionFunctionBase] = {}
        self._lock = asyncio.Lock()  # asyncio.Lock for async-safe synchronization
        self._initialized = True

        logger.info("ExecutionFunctionRegistry initialized")

    async def register(
        self,
        function_type: str,
        function_class: Type[ExecutionFunctionBase],
        override: bool = False,
    ) -> None:
        """Register a new execution function type.

        Args:
            function_type: Unique identifier for function type
            function_class: Class implementing ExecutionFunctionBase
            override: Whether to override existing registration

        Raises:
            ValueError: If function_type already registered and override=False
            TypeError: If function_class doesn't inherit from ExecutionFunctionBase
        """
        if not issubclass(function_class, ExecutionFunctionBase):
            raise TypeError(
                f"{function_class.__name__} must inherit from ExecutionFunctionBase"
            )

        async with self._lock:
            if function_type in self._functions and not override:
                raise ValueError(
                    f"Function type '{function_type}' already registered. "
                    f"Use override=True to replace."
                )

            self._functions[function_type] = function_class
            
        logger.info(
            f"Registered execution function: {function_type} -> "
            f"{function_class.__name__}"
        )

    async def unregister(self, function_type: str) -> bool:
        """Unregister an execution function type.

        Args:
            function_type: Function type to unregister

        Returns:
            True if unregistered, False if not found
        """
        async with self._lock:
            if function_type in self._functions:
                del self._functions[function_type]

                # Remove any instances of this type
                instances_to_remove = [
                    name
                    for name, instance in self._instances.items()
                    if instance.config.function_type == function_type
                ]
                for name in instances_to_remove:
                    del self._instances[name]

                logger.info(f"Unregistered execution function: {function_type}")
                return True

            return False

    async def create_function(self, config: ExecutionFunctionConfig) -> ExecutionFunctionBase:
        """Create and configure an execution function instance.

        Args:
            config: Function configuration

        Returns:
            Configured execution function instance

        Raises:
            ValueError: If function_type not registered
        """
        async with self._lock:
            if config.function_type not in self._functions:
                available = ", ".join(self._functions.keys())
                raise ValueError(
                    f"Unknown function type '{config.function_type}'. "
                    f"Available types: {available}"
                )

            function_class = self._functions[config.function_type]

        try:
            instance = function_class(config)

            # Store instance for management with lock protection
            async with self._lock:
                self._instances[config.name] = instance

            logger.info(
                f"Created function instance '{config.name}' "
                f"of type {config.function_type}"
            )

            return instance

        except Exception as e:
            logger.error(
                f"Failed to create function '{config.name}' "
                f"of type {config.function_type}: {e}"
            )
            raise

    def get_function(self, name: str) -> Optional[ExecutionFunctionBase]:
        """Get an existing function instance by name.

        Args:
            name: Function instance name

        Returns:
            Function instance or None if not found
        """
        return self._instances.get(name)

    async def get_or_create_function(
        self, config: ExecutionFunctionConfig
    ) -> ExecutionFunctionBase:
        """Get existing function or create new one.

        Args:
            config: Function configuration

        Returns:
            Function instance
        """
        existing = self.get_function(config.name)
        if existing:
            return existing

        return await self.create_function(config)

    def list_registered_types(self) -> List[str]:
        """List all registered function types.

        Returns:
            List of registered function type names
        """
        return list(self._functions.keys())

    def list_instances(self) -> List[str]:
        """List all created function instance names.

        Returns:
            List of instance names
        """
        return list(self._instances.keys())

    def get_instance_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a function instance.

        Args:
            name: Function instance name

        Returns:
            Dictionary with instance information or None
        """
        instance = self.get_function(name)
        if not instance:
            return None

        return {
            "name": instance.name,
            "type": instance.config.function_type,
            "timeframe": instance.timeframe.value,
            "enabled": instance.enabled,
            "parameters": instance.parameters,
            "description": instance.description,
            "lookback_bars": instance.lookback_bars,
        }

    def get_functions_by_timeframe(self, timeframe: str) -> List[ExecutionFunctionBase]:
        """Get all functions for a specific timeframe.

        Args:
            timeframe: Timeframe to filter by

        Returns:
            List of function instances for the timeframe
        """
        return [
            instance
            for instance in self._instances.values()
            if instance.timeframe.value == timeframe and instance.enabled
        ]

    def get_functions_by_type(self, function_type: str) -> List[ExecutionFunctionBase]:
        """Get all functions of a specific type.

        Args:
            function_type: Function type to filter by

        Returns:
            List of function instances of the type
        """
        return [
            instance
            for instance in self._instances.values()
            if instance.config.function_type == function_type
        ]

    async def clear_instances(self) -> None:
        """Clear all function instances (keeps registrations)."""
        async with self._lock:
            self._instances.clear()
        logger.info("Cleared all function instances")

    async def clear_all(self) -> None:
        """Clear all registrations and instances."""
        async with self._lock:
            self._functions.clear()
            self._instances.clear()
        logger.info("Cleared all function registrations and instances")

    def __str__(self) -> str:
        """String representation of registry."""
        return (
            f"ExecutionFunctionRegistry("
            f"types={len(self._functions)}, "
            f"instances={len(self._instances)})"
        )

    def __repr__(self) -> str:
        """Detailed representation of registry."""
        return (
            f"ExecutionFunctionRegistry("
            f"registered_types={self.list_registered_types()}, "
            f"instances={self.list_instances()})"
        )




# Global registry instance (module-level singleton - naturally thread-safe)
registry = ExecutionFunctionRegistry()
