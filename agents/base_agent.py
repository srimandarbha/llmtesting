class BaseSreAgent:
    """Base class for all Blackboard agents"""
    def __init__(self, name):
        self.name = name

    def execute(self, state, db_config):
        raise NotImplementedError("Each agent must implement the execute method.")
