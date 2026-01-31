## Feature description
This feature will add a simple command line tool that gets greets 
the user with his name, it doesn't support  CLI flags.

## Acceptance criteria
- it says hello to the user with his full Name as known in Mac OS
- A complete output might look like:
  Hello, Andreas!

## Architecture
The command line tool will be written in Python. 
Put the code for the greeting into the module
- src/helloworld/greeting.py
Put the driver and CLI aspects into src/helloworld/main.py
Put a call to helloworld.main.main() into main.py in the project root

