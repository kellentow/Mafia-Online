def add_global_wrapper(global_dict):
    def wrapper(**kwargs):
        for key, value in kwargs.items():
            if key in global_dict and global_dict[key] != value and not isinstance(global_dict[key], OverwritableGlobal):
                print(f"Warning: Overwriting global variable '{key}'")
            global_dict[key] = value
    return wrapper

class OverwritableGlobal:
    def __init__(self):
        pass