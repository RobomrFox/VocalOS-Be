import subprocess
import sys

def check_and_install_packages(packages):
    """
    Checks if the specified packages are installed, and if not, prompts the user
    to install them using 'uv add' instead of pip.
    """
    for package in packages:
        import_name = package['import_name']
        install_name = package.get('install_name', import_name)
        version = package.get('version', '')

        try:
            __import__(import_name)
        except ImportError:
            user_input = input(
                f"This program requires the '{import_name}' library, which is not installed.\n"
                f"Do you want to install it now? (y/n): "
            )
            if user_input.strip().lower() == 'y':
                try:
                    # Build the uv add command
                    # Note: uv does not support version constraints the way pip does
                    install_command = ["uv", "add", install_name]
                    # Run the command
                    subprocess.check_call(install_command)
                    __import__(import_name)
                    print(f"Successfully installed '{install_name}' using uv.")
                except Exception as e:
                    print(f"An error occurred while installing '{install_name}' with uv: {e}")
                    sys.exit(1)
            else:
                print(f"The program requires the '{import_name}' library to run. Exiting...")
                sys.exit(1)
