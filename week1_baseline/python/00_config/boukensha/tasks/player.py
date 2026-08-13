from boukensha.tasks.base import Base


class Player(Base):
    @classmethod
    def task_name(cls) -> str:
        return "player"
