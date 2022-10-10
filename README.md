<h1 align="center">GFS - Google Form Spammer</h1>
<p align="center">A simple CLI script to spam Google Forms used by various scammers to collect stolen data</p>


<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>


## 💻 Screenshots

<p align="center">
  <a href="https://i.ibb.co/JrQwbqX/demo.png"><img src="https://i.ibb.co/JrQwbqX/demo.png"></a>
</p>


## ✨ Features

- Garbage data generation
- Random option selection in multiple choice questions
- Use of threads for faster request sending
- Filling in non-textual & validated fields
- Form validation


## ➡️ Installation

1. Clone this repository
2. Run the following command

```bash
pip install -r requirements.txt  
```


## 🚩 Usage

To use this script just run the following command after following the Installation Guide

Main command:
```bash
usage: gfs.py [-h] -u URL [-r REQUESTS] [-t THREADS] [--required | --no-required]

GFS v0.6 - A script to spam malicious Google Forms with garbage data

options:
  -h, --help            show this help message and exit
  -u URL, --url URL     The target Google Form URL
  -r REQUESTS, --requests REQUESTS
                        The amount of requests to send [default: 500]
  -t THREADS, --threads THREADS
                        The amount of threads to use [default: 50]
  --required, --no-required
                        If you only want to fill in the required fields (default: False)

```

## 🎉 Contributing

Contributions are always welcome, please make an appropriate Pull Request if you want to contribute


## ❤️ Authors

- [@IlluminatiFish](https://www.github.com/illuminatifish)


## 📝 License

GFS - A piece of software that spams Google Forms with garbage data Copyright (c) 2022 IlluminatiFish

You should have received a copy of the MIT License along with this program. If not, see https://opensource.org/licenses/MIT


## 🏴 Disclaimer 

I am not liable for any malicious activity when people use this script, this was purely made to spam Google Forms that are owned by scammers which reply to specific keywords in tweets with bots and send Google Form links to harvest crypto login credentials
