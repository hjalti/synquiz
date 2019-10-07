class ValidationFailed(Exception):
    def __init__(self, message, data):
        self.message = message
        self.data = data

    def identity(self):
        if 'type' in self.data:
            return self.data.get('title', 'Unknown')
        return 'Quiz metadata'


def required(data, items):
    if isinstance(items, str):
        items = [items]
    for it in items:
        if it not in data:
            raise ValidationFailed(f"'{it}' is required", data)

def mutually_exclusive(data, items):
    if all(x in data for x in items):
        raise ValidationFailed(f"{' and '.join(map(repr,items))} cannot be specified at the same time", data)

def non_empty(data, item):
    if not data.get(item):
        raise ValidationFailed(f"'{item}' cannot be empty", data)

def one_of(data, item, legal):
    if item in data and not data[item] in legal:
        raise ValidationFailed(f"'{item}' must be one of {str(legal)}", data)

