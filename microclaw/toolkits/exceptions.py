class UserDeniedAction(Exception):
    def __init__(self):
        super().__init__("User denied tool action")
