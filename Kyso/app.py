"""Application entry point; smoke mode never touches Chrome or certificates."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    import tkinter as tk
    from kyso.gui import SignerApp
    root = tk.Tk()
    app = SignerApp(root, autoload=not args.smoke_test)
    if args.smoke_test:
        root.after(500, app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
