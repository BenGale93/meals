"""Module containing package specific exceptions."""


class MealsError(Exception):
    """Base class for all Meals errors."""


class RecipeAlreadyExistsError(MealsError):
    def __init__(self, message: str = "Recipe already exists. Choose a different name.") -> None:
        """Initialise with the default message."""
        self.message = message
        super().__init__(self.message)


class RecipeDoesNotExistError(MealsError):
    def __init__(self, message: str = "Recipe does not exist. Use the create endpoint.") -> None:
        """Initialise with the default message."""
        self.message = message
        super().__init__(self.message)


class TimingAlreadyExistsError(MealsError):
    def __init__(self, message: str = "Timing already exists. Edit the existing one.") -> None:
        """Initialise with the default message."""
        self.message = message
        super().__init__(self.message)
