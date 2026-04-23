import time
from prompt_toolkit import prompt
from rich.console import Console

console = Console()

def main():
    while True:
        text = prompt("Enter something: ")
        if not text: break
        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            time.sleep(2)
        print("Done thinking!")

if __name__ == '__main__':
    main()
