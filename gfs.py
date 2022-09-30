import re
import ast
import rstr
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


class ValidatorSubType(Enum):
    """
        An enum to define all possible field validator subtypes.
    """

    GREATER_THAN = 1
    GREATER_THAN_OR_EQUAL_TO = 2
    LESS_THAN = 3
    LESS_THAN_OR_EQUAL_TO = 4
    EQUAL_TO = 5
    NOT_EQUAL_TO = 6
    BETWEEN = 7
    NOT_BETWEEN = 8
    IS_NUMBER = 9
    WHOLE_NUMBER = 10

    CONTAINS = 100
    NOT_CONTAINS = 101
    EMAIL = 102
    URL = 103

    SELECT_AT_LEAST = 200
    SELECT_AT_MOST = 201
    SELECT_EXACTLY = 204

    MAX_CHAR_COUNT = 202
    MIN_CHAR_COUNT = 203

    REGEX_CONTAINS = 299
    REGEX_NOT_CONTAINS = 300
    REGEX_MATCH = 301
    REGEX_NOT_MATCH = 302


class ValidatorType(Enum):
    """
        An enum to define all possible field validator types.
    """

    NUMBER = 1
    TEXT = 2
    LENGTH = 3
    REGEX = 4

    PARAGRAPH_LENGTH = 6
    CHECKBOX_SELECT = 7


class FieldType(Enum):
    """
        An enum to define all possible field types.
    """

    SHORT_ANSWER = 0
    PARAGRAPH = 1
    MULTIPLE_CHOICE = 2
    DROPDOWN = 3
    CHECKBOXES = 4
    LINEAR_SCALE = 5
    MULTIPLE_CHOICE_GRID = 7
    CHECKBOX_GRID = 8
    DATE = 9
    TIME = 10


class Field(object):
    """
        An object used to define fields.
    """

    validation: bool
    required: bool
    has_choices: bool

    def __init__(self):
        self.type = None
        self.name = None
        self.id = None
        self.choices = []
        self.validator = None
        self.validator_type = None
        self.validator_sub_type = None
        self.validation_error = ''
        self.is_extended_type = None


class Choice(object):
    """
        An object used to define field choices.
    """

    def __init__(self):
        self.choice_name = None


class GFSLogger:
    """
        Logger class, used to send logging messages to the CLI
    """
    def __init__(self, level, message):
        self.level = level
        self.message = message
        self.color_codes = {
            'ERROR':  'FF0000',
            'WARNING': 'EDB810'
        }

        color_code = self.color_codes.get(self.level, 'FFFFFF')
        print(f'[bold #{color_code}][{self.level}]: {self.message}[/bold #{color_code}]')

        if self.level == 'ERROR':
            exit(1)


class GoogleFormSpammer:

    VERSION = '0.5'

    def __init__(self, form_url: str = None, required_only: bool = False) -> None:
        """
            Constructor for the GoogleFormSpammer class.

            Args:
                form_url (str): The URL of the form to be used.
                required_only (bool): If you only want to fill in the required fields.
        """

        FORM_URL_REGEX = "https://docs\.google\.com/forms/d/e/[A-Za-z0-9_-]{56}/formResponse"

        if form_url is None:
            GFSLogger("ERROR", "form_url cannot be None")

        if not re.match(
            FORM_URL_REGEX, form_url
        ):
            GFSLogger("ERROR", f"form_url is not valid, must match the following regex {FORM_URL_REGEX}")

        self.form_url = form_url
        self.required_only = required_only
        self.scraped_data = self._scrape_form()

        self.successful_request = 0
        self.errors = {}


    def _scrape_form(self) -> List[Field]:
        """
            A function to scrape the form to get all the required post data.

            Returns:
                fields (List[Field]): A list of fields from the scraped form data.
        """

        response = requests.get(self.form_url)

        if response.status_code != 200:
            GFSLogger(
                "ERROR",
                f"Exception occurred while scraping form, expected status code 200 but got {response.status_code}"
            )

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

            if "jsmodel" not in div.attrs.keys():
                continue

            data_params = div.attrs.get("data-params")

            # Fix array so it can be handled by Python
            for old, new in replacements.items():
                data_params = data_params.replace(old, new)

            # Literal eval the string list
            data_params_eval = ast.literal_eval(data_params)

            if not isinstance(data_params_eval, list):
                GFSLogger(
                    "ERROR",
                    f"Expected data parameters to be a list got type {type(data_params_eval).__name__}"
                )

            response_data = data_params_eval[0][4]

            # Create a new Field object for each field we come across
            field = Field()

            # Populate the attributes with the parsed field data
            field.type = FieldType(data_params_eval[0][3])
            field.name = data_params_eval[0][1]
            field.id = response_data[0][0]

            if field.type == FieldType.DATE:
                field.is_extended_type = True if response_data[0][7][0] == 'true' else False

            elif field.type == FieldType.TIME:
                field.is_extended_type = True if response_data[0][6][0] == 'true' else False

            field.validation = False

            if len(response_data[0][4]) > 0:

                validation_metadata = response_data[0][4][0]

                validator_type = validation_metadata[0]
                validator_sub_type = validation_metadata[1]
                validators = validation_metadata[2]

                field.validation = True

                try:
                    field.validator_type = ValidatorType(validator_type)
                except ValueError:
                    GFSLogger(
                        "ERROR",
                        f"Unsupported ValidatorType (type={validator_type}) found with Field(id={field.id})"
                    )

                try:
                    field.validator_sub_type = ValidatorSubType(validator_sub_type)
                except ValueError:
                    GFSLogger(
                        "ERROR",
                        f"Unsupported ValidatorSubType(type={validator_sub_type}|parent={validator_type}) found with Field(id={field.id})"
                    )

                no_validators = all(validator == '' or not validator for validator in validators)

                field.validator = None if no_validators else validators
                field.validation_error = validation_metadata[3] if len(validation_metadata) >= 4 else None

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

    def generate_post_data(self, data_length: int = 80) -> Dict[str, str]:
        """
            A function to scrape the form to get all the required post data.

            Args:
                data_length (int): The length of the garbage data that is sent, defaults to 80.

            Returns:
                post_data (Dict[str, str]): A dictionary of the post data.
        """

        post_data = {}
        chars = string.ascii_letters + string.digits

        scraped_form_data = self.scraped_data

        # Gets the list of only required fields if you do not want to fill the whole form
        if self.required_only:
            scraped_form_data = [field for field in self.scraped_data if field.required]

        # Fields that have validation attached to them
        VALIDATED_FIELDS = (
            FieldType.SHORT_ANSWER,
            FieldType.PARAGRAPH,
            FieldType.CHECKBOXES
        )

        SUBVALIDATORS_WITH_NO_VALIDATION = (
            ValidatorSubType.URL,
            ValidatorSubType.EMAIL,
            ValidatorSubType.IS_NUMBER,
            ValidatorSubType.WHOLE_NUMBER
        )

        for field in scraped_form_data:

            if field.type == FieldType.TIME:

                post_data[f"entry.{field.id}_hour"] = f"{random.randint(0, 23):02d}"
                post_data[f"entry.{field.id}_minute"] = f"{random.randint(0, 59):02d}"

                if field.is_extended_type:
                    post_data[f"entry.{field.id}_second"] = f"{random.randint(0, 59):02d}"

            elif field.type == FieldType.DATE:
                post_data[f"entry.{field.id}_year"] = str(random.randint(1, 2022))
                post_data[f"entry.{field.id}_month"] = str(random.randint(1, 12))
                post_data[f"entry.{field.id}_day"] = str(random.randint(1, 31))

                if field.is_extended_type:
                    post_data[f"entry.{field.id}_hour"] = f"{random.randint(0, 23):02d}"
                    post_data[f"entry.{field.id}_minute"] = f"{random.randint(0, 59):02d}"

            else:
                field_value = None

                if (
                    field.validation  # Does the field have response validation enabled
                    and
                    field.validator is None  # Does the field have a validator associated to the response validation
                    and
                    field.validator_sub_type not in SUBVALIDATORS_WITH_NO_VALIDATION  # Does the validation subtype have a validator

                ):
                    GFSLogger(
                        "WARNING",
                        f"Detected Field(id={field.id}|type={field.type}) with validation but no validator, skipping this field."
                    )


                elif field.type in VALIDATED_FIELDS:

                    if field.type == FieldType.PARAGRAPH:

                        # The REGEX & LENGTH set of validators are exclusive to the SHORT_ANSWER & PARAGRAPH field types

                        if field.validator_type == ValidatorType.REGEX:

                            if field.validator_sub_type in (
                            ValidatorSubType.REGEX_MATCH, ValidatorSubType.REGEX_CONTAINS):
                                field_value = rstr.xeger(field.validator[0])

                            elif field.validator_sub_type in (
                                    ValidatorSubType.REGEX_NOT_MATCH, ValidatorSubType.REGEX_NOT_CONTAINS
                            ):
                                # Special thanks to Daniel for this (https://stackoverflow.com/a/957581)
                                field_value = rstr.xeger(f'^((?!{field.validator[0]}).)*$')

                        elif field.validator_type == ValidatorType.PARAGRAPH_LENGTH:

                            validator_length = int(field.validator[0])

                            if field.validator_sub_type == ValidatorSubType.MAX_CHAR_COUNT:
                                field_value = "".join(
                                    random.choice(chars) for _ in range(validator_length - 1)
                                )

                            elif field.validator_sub_type == ValidatorSubType.MIN_CHAR_COUNT:
                                field_value = "".join(
                                    random.choice(chars) for _ in range(validator_length + 1)
                                )

                        else:
                            field_value = "".join(
                                random.choice(chars) for _ in range(data_length)
                            )

                    elif field.type == FieldType.SHORT_ANSWER:
                        # The TEXT & NUMBER set of validators are exclusive to the SHORT_ANSWER field type

                        if field.validator_type == ValidatorType.TEXT:

                            # Fields that require emails as input
                            if field.validator_sub_type == ValidatorSubType.EMAIL:

                                email_providers = [
                                    "yahoo.com",
                                    "hotmail.com",
                                    "outlook.net",
                                    "gmail.com",
                                ]
                                field_value = "".join(random.choice(chars) for _ in range(data_length)) + "@" + random.choice(email_providers)

                            elif field.validator_sub_type == ValidatorSubType.URL:
                                field_value = rstr.xeger("http[s]?:\/\/[a-zA-Z0-9-]{2,9}\.[a-zA-Z0-9-]{2,60}\.[a-zA-Z]{2,7}")

                            elif field.validator_sub_type == ValidatorSubType.CONTAINS:
                                field_value = field.validator[0]

                            elif field.validator_sub_type == ValidatorSubType.NOT_CONTAINS:
                                field_value = rstr.xeger(f'^((?!{field.validator[0]}).)*$')

                            else:
                                field_value = "".join(
                                    random.choice(chars) for _ in range(data_length)
                                )

                        elif field.validator_type == ValidatorType.REGEX:

                            if field.validator_sub_type in (
                            ValidatorSubType.REGEX_MATCH, ValidatorSubType.REGEX_CONTAINS):
                                field_value = rstr.xeger(field.validator[0])

                            elif field.validator_sub_type in (
                                    ValidatorSubType.REGEX_NOT_MATCH, ValidatorSubType.REGEX_NOT_CONTAINS
                            ):
                                # Special thanks to Daniel for this (https://stackoverflow.com/a/957581)
                                field_value = rstr.xeger(f'^((?!{field.validator[0]}).)*$')

                        elif field.validator_type == ValidatorType.LENGTH:

                            validator_length = int(field.validator[0])

                            if field.validator_sub_type == ValidatorSubType.MAX_CHAR_COUNT:
                                field_value = "".join(
                                    random.choice(chars) for _ in range(validator_length - 1)
                                )

                            elif field.validator_sub_type == ValidatorSubType.MIN_CHAR_COUNT:
                                field_value = "".join(
                                    random.choice(chars) for _ in range(validator_length + 1)
                                )

                        elif field.validator_type == ValidatorType.NUMBER:

                            # Check if the validator is a 'range' to check between
                            is_ranged = len(field.validator) == 2

                            if is_ranged:
                                left, right = [int(validator) for validator in field.validator]
                            else:
                                value = int(field.validator[0])

                            if field.validator_sub_type == ValidatorSubType.GREATER_THAN:
                                field_value = random.randint(value - 1, 5000)

                            elif field.validator_sub_type == ValidatorSubType.GREATER_THAN_OR_EQUAL_TO:
                                field_value = random.randint(value, 5000)

                            elif field.validator_sub_type == ValidatorSubType.LESS_THAN:
                                field_value = random.randint(0, value - 1)

                            elif field.validator_sub_type == ValidatorSubType.LESS_THAN_OR_EQUAL_TO:
                                field_value = random.randint(0, value)

                            elif field.validator_sub_type == ValidatorSubType.EQUAL_TO:
                                field_value = random.choice([i for i in range(1, 20) if i == value])

                            elif field.validator_sub_type == ValidatorSubType.NOT_EQUAL_TO:
                                field_value = random.choice([i for i in range(1, 20) if i != value])

                            elif field.validator_sub_type in (ValidatorSubType.WHOLE_NUMBER, ValidatorSubType.IS_NUMBER):
                                field_value = 1

                            elif field.validator_sub_type == ValidatorSubType.NOT_BETWEEN:
                                field_value = random.choice(
                                    [i for i in range(1, 20) if i not in list(range(left, right))])

                            elif field.validator_sub_type == ValidatorSubType.BETWEEN:
                                field_value = random.choice(range(left, right + 1))

                        else:
                            field_value = "".join(
                                random.choice(chars) for _ in range(data_length)
                            )

                    elif field.type == FieldType.CHECKBOXES:

                        if field.validator_type == ValidatorType.CHECKBOX_SELECT:

                            select_count = int(field.validator[0])

                            choices = field.choices.copy()

                            # Having more selections to make than choices is not possible,
                            # exit program gracefully with appropriate error message
                            if select_count > len(choices):
                                GFSLogger("ERROR", f"Found issue with Field(id={field.id}), cannot select {select_count} options as only {len(choices)} options exist!")

                            # Is there only one selection to be made, if so
                            # select a random option as set it as the field value
                            if select_count == 1:
                                field_value = random.choice(choices).choice_name

                            if field.validator_sub_type in (
                                    ValidatorSubType.SELECT_AT_LEAST,
                                    ValidatorSubType.SELECT_EXACTLY,
                                    ValidatorSubType.SELECT_AT_MOST
                            ):

                                random_selected_options = []

                                for _ in range(select_count):

                                    random_choice = random.choice(choices)

                                    # Other option field detected
                                    if random_choice.choice_name == '':
                                        random_selected_options.append('__other_option__')
                                        post_data[f"entry.{field.id}.other_option_response"] = "".join(
                                                                                                random.choice(chars) for _ in range(data_length)
                                                                                            )
                                    else:
                                        random_selected_options.append(random_choice.choice_name)

                                    # Remove selected choice from choices list,
                                    # prevents it from being selected more than once
                                    choices.remove(random_choice)

                                field_value = random_selected_options

                        else:
                            field_value = random.choice(field.choices).choice_name

                elif field.has_choices:
                    field_value = random.choice(field.choices).choice_name

                post_data[f'entry.{field.id}'] = field_value

        return post_data

    def post_data(self) -> int:
        """
            A function to post the data to the form.

            Returns:
                response.status_code (int): An integer stating the HTTP status code of the response
        """
        generated_post_data = self.generate_post_data()
        response = requests.post(self.form_url, params=generated_post_data)
        return response.status_code

    def threader(self) -> None:
        """
            A function to be used as a target function in the threading code.
        """
        while True:
            _ = queue.get()

            status_code = self.post_data()
            if status_code == 200:
                self.successful_request += 1
            else:
                if status_code not in self.errors.keys():
                    self.errors[status_code] = 1
                else:
                    self.errors[status_code] += 1
            queue.task_done()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description=f"GFS v{GoogleFormSpammer.VERSION} - A script to spam malicious Google Forms with garbage data")

    parser.add_argument("-u", "--url", type=str, required=True, help="The target Google Form URL")
    parser.add_argument("-r", "--requests", type=int, default=500, help="The amount of requests to send [default: 500]")
    parser.add_argument("-t", "--threads", type=int, default=50, help="The amount of threads to use [default: 50]")

    parser.add_argument("--required", action=argparse.BooleanOptionalAction, default=False, required=False, help="If you only want to fill in the required fields")

    args = parser.parse_args()

    if args.url is None:
        GFSLogger("ERROR", "Invalid argument, supply a form url")

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
    success_ratio = round((spammer.successful_request / args.requests) * 100, 2)
    req_per_sec = round(spammer.successful_request / total_time, 3)

    error_messages = {
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        429: 'Too Many Requests',
        500: 'Internal Server Error',
        503: 'Service Unavailable',
        504: 'Gateway Timeout'
    }

    print("\n[bold #07FA1C][=] Spammer finished![/bold #07FA1C]\n")

    completion_table = [
            ["Execution Time", f"{total_time}s"],
            ["Success Ratio", f"{spammer.successful_request}/{args.requests} ({success_ratio}%)"],
            ["Speed", f"{req_per_sec} req/s"],
    ]

    # Check if any errors were caught
    if len(spammer.errors.keys()) > 0:
        errors = ''
        for status, count in spammer.errors.items():
            errors += f'    - {count} requests ({status}, {error_messages.get(status, "Unsupported Status Code")})\n'
        completion_table.append(['Errors', errors])

    results_table = tabulate(
        completion_table,
        tablefmt="pretty",
        colalign=("center", "left"),
    )
    print(f"[bold #31EE42]{results_table}[/bold #31EE42]\n")
