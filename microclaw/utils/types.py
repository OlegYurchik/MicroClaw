class _EmptyMeta(type):
    def __instancecheck__(self, instance):
        if instance is self:
            return True
        return super().__instancecheck__(instance)

    def __call__(cls, *args, **kwargs):
        return cls


class Empty(metaclass=_EmptyMeta):
    pass
