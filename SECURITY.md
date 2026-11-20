# Security and privacy

## Report a security issue

Use [Report a vulnerability](https://github.com/Methos801/PyDocent/security/advisories/new) to contact the maintainers privately. Use fictional data and include the affected version, browser, and steps to reproduce. Learners can ask a parent or trusted adult for help reporting a concern. Keep security details, credentials, and personal learner information out of public issues.

## Local execution

Run PyDocent locally in an updated browser. Learner code runs in a disposable WebAssembly worker on a separate loopback origin. The launcher supplies lessons and stores progress. A Stop button and a time limit end the worker. The worker relies on browser isolation and has no hard memory quota. Challenge feedback and XP are for practice.

The launcher is intended for a local user on their own device. Hosting the Flask server for other people is outside this preview's scope. Saved progress is a local file. Anyone with access to that file can read it.
