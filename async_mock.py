import asyncio
import collections


def async_mock_method(func):
    return _Method(func)


class _Method:
    def __init__(self, func):
        self._func = func

    def __get__(self, instance, owner=None):
        method = _BoundMethod(self._func, instance)
        setattr(instance, self._func.__name__, method)
        return method


class _BoundMethod:
    def __init__(self, func, instance):
        self._func = func
        self._instance = instance
        self.side_effect = None

    async def __call__(self, *args, **kwargs):
        try:
            return await self._func(self._instance, *args, **kwargs)
        finally:
            if self.side_effect:
                side_effect, *self.side_effect = self.side_effect
                if asyncio.iscoroutine(side_effect):
                    return await side_effect
                else:
                    return side_effect(self._instance, *args, **kwargs)
