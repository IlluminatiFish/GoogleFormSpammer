import re
import ast
import time
import random
import string
import requests
import argparse

from enum import Enum
from rich import print
from queue import Queue
from threading import Thread
from tabulate import tabulate
from bs4 import BeautifulSoup
from typing import Dict, List


class FieldType(Enum):
    """
    An enum to define all possible field types
    """

    SHORT_TEXT = 0
    LONG_TEXT = 1
    MULTIPLE_CHOICE = 2
    CHECKBOX = 3
    DROPDOWN = 4
    LINEAR_SCALE = 5
    MULTI_CHOICE_GRID = 7
    DATE = 9
    TIME = 10


class Field(object):
    """
    A Field object used to define fields
    """

    validation: bool
    required: bool
    has_choices: bool

    def __init__(self):
        self.type = None
        self.name = None
        self.id = None
        self.choices = []


class Choice(object):
    """
    A Choice object used to define choices
    """

    def __init__(self):
        self.choice_name = None


class GoogleFormSpammerException(Exception):
    """
    A class to be raised when errors occur
    """

    pass


class GoogleFormSpammer:
    """
    A class to hold all functions for the script
    """

    def __init__(self, form_url: str = None, required_only: bool = False) -> None:
        """
        The class constructor

            Parameters:
                form_url (str): The URL of the form to be used
                required_only (bool): If you only want to fill in the required fields

            Raises:
                GoogleFormSpammerException: If `form_url` is None or if it is not a valid form url
        """
        if form_url is None:
            raise GoogleFormSpammerException("form_url cannot be None")

        if not re.match(
            "https://docs.google.com/forms/d/e/[A-Za-z0-9_-]{56}/formResponse", form_url
        ):
            raise GoogleFormSpammerException("form_url is not valid")

        self.form_url = form_url
        self.required_only = required_only
        self.scraped_data = self._scrape_form()

    def _scrape_form(self) -> List[Field]:
        """
        A function to scrape the form to get all the required post data

            Returns:
                fields (List[Field]): A list of fields from the scraped form data

        """
        response = requests.get(self.form_url)
        soup = BeautifulSoup(response.text, "html.parser")

        divs = soup.find_all("div")

        replacements = {
            "%.@.": "[",
            "null": '"null"',
            "true": '"true"',
            "false": '"false"',
        }

        fields = []

        for div in divs:

            # Find all div tags with the attribute `jsmodel`
            if "jsmodel" in div.attrs.keys():

                data_params = div.attrs.get("data-params")

                # Fix array so it can be handled by Python
                for old, new in replacements.items():
                    data_params = data_params.replace(old, new)

                # Literal eval the string list
                data_params_eval = ast.literal_eval(data_params)

                response_data = data_params_eval[0][4]

                # Create a new Field object for each field we come across
                field = Field()

                # Populate the attributes with the parsed field data
                field.type = FieldType(data_params_eval[0][3])
                field.name = data_params_eval[0][1]
                field.id = response_data[0][0]

                field.validation = len(response_data[0][4]) > 0
                field.required = True if response_data[0][2] == "true" else False
                field.has_choices = False

                if len(response_data[0][1]) > 0:

                    choices = []

                    for raw_choice in response_data[0][1]:

                        choice = Choice()
                        choice.choice_name = raw_choice[0]
                        choices.append(choice)

                    field.has_choices = len(choices) > 0
                    field.choices = choices

                fields.append(field)

        return fields

    def generate_post_data(self, data_length: int = 50) -> Dict[str, str]:
        """
        A function to scrape the form to get all the required post data

            Parameters:
                data_length (int): The length of the garbage data that is sent

            Returns:
                post_data (Dict[str, str]): A dictionary of the post data

        """
        post_data = {}
        chars = string.ascii_letters + string.digits

        scraped_form_data = self.scraped_data

        # Gets the list of only required fields if you do not want to fill the whole form
        if self.required_only:
            scraped_form_data = [field for field in self.scraped_data if field.required]

        for field in scraped_form_data:

            # To support the date and time fields we must make a specific case for each
            if field.type == FieldType.TIME:
                post_data[f"entry.{field.id}_hour"] = f"{random.randint(0, 23):02d}"
                post_data[f"entry.{field.id}_minute"] = f"{random.randint(0, 59):02d}"

            elif field.type == FieldType.DATE:
                post_data[f"entry.{field.id}_year"] = str(random.randint(2000, 2022))
                post_data[f"entry.{field.id}_month"] = str(random.randint(1, 12))
                post_data[f"entry.{field.id}_day"] = str(random.randint(1, 31))

            else:

                # Only field that has validation is the email fields if found
                if field.validation:
                    email_providers = [
                        "yahoo.com",
                        "hotmail.com",
                        "outlook.net",
                        "gmail.com",
                    ]
                    selected_choice = "".join(random.choice(chars) for _ in range(data_length)) + "@" + random.choice(email_providers)

                elif field.has_choices:
                    selected_choice = random.choice(field.choices).choice_name

                else:
                    selected_choice = "".join(
                        random.choice(chars) for _ in range(data_length)
                    )

                post_data[f"entry.{field.id}"] = selected_choice

        return post_data

    def post_data(self) -> int:
        """
        A function to post the data to the form

            Returns:
                response.status_code (int): An integer stating the HTTP status code of the response

        """
        response = requests.post(self.form_url, params=self.generate_post_data())
        return response.status_code

    def threader(self) -> None:
        """
        A function to be used as a target function in the threading
        """
        while True:
            _ = queue.get()
            self.post_data()
            queue.task_done()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="A script to spam Google Forms with garbage data")

    parser.add_argument("-u", "--url", type=str, required=True, help="The url of the google form")
    parser.add_argument("-o", "--required", type=bool, default=False, help="If you only want to fill in the required fields")
    parser.add_argument("-r", "--requests", type=int, default=500, help="The amount of requests to execute")
    parser.add_argument("-t", "--threads", type=int, default=50, help="The amount of threads to use")

    args = parser.parse_args()

    if args.url is None:
        print(f"[bold #F04349][-] Invalid argument, supply a form url[/bold #F04349]")
        exit(-1)

    print("")
    print("[bold #FC970F][~] Starting spammer...[/bold #FC970F]\n")
    parameter_table = tabulate(
        [
            ["URL", args.url],
            ["Requests", args.requests],
            ["Threads", args.threads],
            ["Required Fields", args.required],
        ],
        tablefmt="pretty",
        colalign=("center", "left"),
    )
    print(f"[bold #F2B44B]{parameter_table}[/bold #F2B44B]\n")

    spammer = GoogleFormSpammer(args.url, args.required)

    start = time.perf_counter()

    queue = Queue()

    for _ in range(args.threads):
        worker = Thread(target=spammer.threader)
        worker.daemon = True
        worker.start()

    for request_worker in range(args.requests):
        queue.put(request_worker)

    queue.join()

    total_time = round(time.perf_counter() - start, 2)
    req_per_sec = round(args.requests / total_time, 3)

    print("[bold #07FA1C][=] Spammer finished![/bold #07FA1C]\n")
    results_table = tabulate(
        [
            ["Execution Time", f"{total_time}s"],
            ["Speed", f"{req_per_sec} req/s"]
        ],
        tablefmt="pretty",
        colalign=("center", "left"),
    )
    print(f"[bold #31EE42]{results_table}[/bold #31EE42]\n")
