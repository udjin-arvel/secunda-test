from sqlalchemy.orm import DeclarativeBase


def enum_values(enum_cls: type) -> list[str]:
    return [member.value for member in enum_cls]


class Base(DeclarativeBase):
    pass
