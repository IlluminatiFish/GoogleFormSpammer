import re
import ast
import time
import random
import string
import requests
import argparse

from rich import print
from queue import Queue
from threading import Thread
from bs4 import BeautifulSoup

class GoogleFormSpammerException(Exception):
    """
    A class to be raised when errors occur
    """
    pass

class GoogleFormSpammer:
    """
    A class to hold all functions for the script
    """
    def __init__(self, form_url: str = None) -> None:
        """
        The class constructor

            Parameters:
                form_url (str): The URL of the form to be used

            Returns:
                None

            Raises:
                GoogleFormSpammerException: If `form_url` is None or if it is not a valid form url
        """
        if form_url is None:
            raise GoogleFormSpammerException('form_url cannot be None')

        if not re.match('https://docs.google.com/forms/d/e/[A-Za-z0-9_-]{56}/formResponse', form_url):
            raise GoogleFormSpammerException('form_url is not valid')

        self.form_url = form_url

    def _scrape_form(self) -> dict:
        """
        A function to scrape the form to get all the required post data

            Parameters:
                None

            Returns:
                scraped_data (dict): A dictionary of the scraped form data

            Raises:
                None
        """
        scraped_data = {}

        response = requests.get(self.form_url)

        soup = BeautifulSoup(response.text, 'html.parser')
        divs = soup.find_all('div')

        replacements = {'%.@.': '[', 'null': '"null"', 'true': '"true"', 'false': '"false"'}

        for div in divs:
            # Find all div tags with the attribute `jsmodel`
            if 'jsmodel' in div.attrs.keys():
                data_params = div.attrs.get('data-params')

                # Fix array so it can be handled by Python
                for old, new in replacements.items():
                    data_params = data_params.replace(old, new)

                # Literal eval the string list
                data_params_eval = ast.literal_eval(data_params)

                question = data_params_eval[0][1]
                response_data = data_params_eval[0][4]

                entry_id = response_data[0][0]
                multi_option_responses = response_data[0][1]

                possible_responses = [multi_option_response[0] for multi_option_response in multi_option_responses]

                if len(multi_option_responses) > 0:
                    scraped_data[question] = (entry_id, True, possible_responses)
                else:
                    scraped_data[question] = (entry_id, False, None)

        return scraped_data

    def generate_post_data(self, data_length: int = 50) -> dict:
        """
        A function to scrape the form to get all the required post data

            Parameters:
                data_length (int): The length of the garabage data that is sent

            Returns:
                post_data (dict): A dictionary of the post data

            Raises:
                None
        """
        chars = string.ascii_letters + string.digits
        scraped_data = self._scrape_form()
        post_data = {}

        for _, (entry_id, is_multi_option, options) in scraped_data.items():
            if is_multi_option:
                selected_option = random.choice(options)
            else:
                selected_option = ''.join(random.choice(chars) for _ in range(data_length))

            post_data[f'entry.{entry_id}'] = str(selected_option)

        return post_data

    def post_data(self) -> int:
        """
        A function to post the data to the form

            Parameters:
                None

            Returns:
                response.status_code (int): An integer stating the HTTP status code of the webserver

            Raises:
                None
        """
        response = requests.post(self.form_url, params=self.generate_post_data())
        return response.status_code

    def threader(self) -> None:
        """
        A function to be used as a target function in the threading

            Parameters:
                None

            Returns:
                None

            Raises:
                None
        """
        while True:
            worker = queue.get()
            self.post_data()
            queue.task_done()

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='A Google form spamming script')

    parser.add_argument('-r', '--requests', type=int, default=500, help='The amount of requests to execute')
    parser.add_argument('-u', '--url', type=str, help='The url of the google form')
    parser.add_argument('-t', '--threads', type=int, default=500, help='The amount of threads to use')

    args = parser.parse_args()

    if args.url is None:
        print(f'[bold #F04349]Invalid argument, supply a form url[/bold #F04349]')
        exit(-1)

    try:
        spammer = GoogleFormSpammer(args.url)
    except GoogleFormSpammerException as exception:
        print('[bold #F04349]Invalid url was supplied[/bold #F04349]')
        exit(-1)
    
    print(f'[bold #54E81E]Starting spammer on URL [bold #34EDE7]{args.url}[/bold #34EDE7] with [bold #34EDE7]{args.requests}[/bold #34EDE7] requests and [bold #34EDE7]{args.threads}[/bold #34EDE7] threads[/bold #54E81E]')


    start = time.perf_counter()

    queue = Queue()

    for _ in range(args.threads):
        worker = Thread(target=spammer.threader)
        worker.daemon = True
        worker.start()

    for worker in range(args.requests):
        queue.put(worker)

    queue.join()

    total_time = time.perf_counter() - start
    req_per_ns = args.requests / total_time
    
    print('[bold #07FA1C]Script finished![/bold #07FA1C]')
    print(f'[bold #2ECC71]Requests sent: {args.requests} req[/bold #2ECC71]')
    print(f'[bold #2ECC71]Execution time: {total_time}s[/bold #2ECC71]')
    print(f'[bold #2ECC71]Speed: {req_per_ns} req/s[/bold #2ECC71]')
