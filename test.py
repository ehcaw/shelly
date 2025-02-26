from textual_components.architect.architect import Architect
from textual.app import App

if __name__ == "__main__":
    my_app = App()
    my_app.mount(Architect())
    my_app.run()
