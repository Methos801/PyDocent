# PyDocent

**Your guide to learning Python**

PyDocent is a free, open-source project for beginners. Its eight short lessons go from writing a first greeting to building a small program with input, lists, loops, and functions. Every lesson includes examples to try, hints, and a challenge.

**Status: work in progress.** This preview runs locally from source. After setup, lessons work offline in Chrome or Edge.

![PyDocent lesson workspace showing the code editor, program output and challenge feedback](docs/lesson-preview.png)

## How the feedback catches a shortcut

In the conditionals lesson, the goal is to classify ages, not merely to print the answer for the number in the editor. Suppose the example starts at 16. Hard-coding “You are a minor” looks correct until the checker replaces the age and runs the program again.

| Check | Hard-coded answer | Conditional answer |
| --- | --- | --- |
| Age 17 | Prints “You are a minor” | Prints “You are a minor” |
| Age 18 | Still prints “You are a minor” | Prints “You are an adult” |

The checker runs both sides of the boundary and accepts different valid ways to write the condition. A learner gets feedback about the behavior, not a demand to copy one solution. The example illustrates the check; PyDocent runs the learner’s code locally in a browser Worker.


## Try it locally

Download or clone the source and open a terminal in the PyDocent folder. With Python 3.14 installed, run these commands on Windows:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe fetch_runtime.py
.venv\Scripts\python.exe app.py
```

The setup downloads the Python dependencies and a verified browser runtime. When the app opens, choose **Start learning** or pick any lesson. If your browser does not open automatically, visit http://127.0.0.1:5001/. Click **Quit** when you are done.

On macOS or Linux, use `python3` to create the environment and `.venv/bin/python` for the subsequent commands. This preview was tested on Windows.

## What to expect

- Run real Python and get feedback on each lesson challenge.
- Use the highlighted editor or switch to a plain-text editor.
- Use imaginary names and ages in examples. Code, sample input and XP are saved in `progress.json` in this folder.
- Use **Erase saved work** to clear that copy. If you made backups, manage those separately.

PyDocent runs learner code in a disposable browser worker. See the [local execution and reporting policy](SECURITY.md) and [accessibility notes](ACCESSIBILITY.md).

For ordinary bugs, open an issue with the lesson, browser, and steps to reproduce. Use fictional data in examples and screenshots. Original code and lessons use the [MIT License](LICENSE). The editor and downloaded runtime have separate [third-party terms](THIRD_PARTY_NOTICES.md).
