import random
import datetime
import os, sys, re
import json
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

PROJECT_PATH = os.environ.get("PROJECT_PATH")
DATA_PATH = os.path.join(PROJECT_PATH, "data")
IMG_PATH = os.path.join(PROJECT_PATH, "imgs")
PAGE_PATH = os.path.join(PROJECT_PATH, "front_page")
sys.path.append(PROJECT_PATH)

url = "https://twitter.com/login"
username = os.getenv("TWITTER_EMAIL")
userpass = os.getenv("TWITTER_PASSWORD")
phone = os.getenv("TWITTER_PHONE")

import utils.vector_store as vs
import utils.db as db


def bold(input_text, extra_str):
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    bold_chars = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    bold_italic_chars = "𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕𝙖𝙗𝙘𝙙𝙚𝙛𝙜𝙝𝙞𝙟𝙠𝙡𝙢𝙣𝙤𝙥𝙦𝙧𝙨𝙩𝙪𝙫𝙬𝙭𝙮𝙯𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"

    # Helper function to bold the characters within quotes
    def boldify(text):
        bolded_text = ""
        for character in text:
            if character in chars:
                bolded_text += bold_chars[chars.index(character)]
            else:
                bolded_text += character
        return bolded_text

    # Helper function to bold and italicize the characters within asterisks
    def bold_italicize(text):
        bold_italic_text = ""
        for character in text:
            if character in chars:
                bold_italic_text += bold_italic_chars[chars.index(character)]
            else:
                bold_italic_text += character
        return bold_italic_text

    ## Regex to find text in quotes and apply the boldify function to them.
    output = re.sub(
        r'"([^"]*)"',
        lambda m: '"' + boldify(m.group(1)) + '" (' + extra_str + ")",
        input_text,
    )
    output = output.replace('"', "")
    # Regex to find text in double asterisks and apply the bold_italicize function to them
    output = re.sub(r"\*\*([^*]*)\*\*", lambda m: bold_italicize(m.group(1)), output)

    return output.strip()


def send_tweet(tweet_content, tweet_image_path, tweet_page_path, post_tweet):
    browser = webdriver.Firefox()
    browser.get(url)

    ## Login.
    user = WebDriverWait(browser, 30).until(
        EC.presence_of_element_located(
            (By.XPATH, '//input[@name="text" and @autocomplete="username"]')
        )
    )
    user.send_keys(username)
    user.send_keys(Keys.ENTER)

    ## Sometimes phone number is required.
    try:
        number = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
            )
        )
        number.send_keys(phone)
        number.send_keys(Keys.ENTER)
    except:
        ## Try again.
        user = WebDriverWait(browser, 30).until(
            EC.presence_of_element_located(
                (By.XPATH, '//input[@name="text" and @autocomplete="username"]')
            )
        )
        user.send_keys(username)
        user.send_keys(Keys.ENTER)

        try:
            number = WebDriverWait(browser, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
                )
            )
            number.send_keys(phone)
            number.send_keys(Keys.ENTER)
        except:
            raise Exception("Failed to login.")


    password = WebDriverWait(browser, 30).until(
        EC.presence_of_element_located((By.NAME, "password"))
    )
    password.send_keys(userpass)
    password.send_keys(Keys.ENTER)

    ## Upload first image.
    input_box = WebDriverWait(browser, 30).until(
        EC.presence_of_element_located((By.XPATH, "//input[@accept]"))
    )
    input_box.send_keys(tweet_image_path)

    ## Wait for the first image to be uploaded and processed.
    WebDriverWait(browser, 30).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[data-testid='attachments']")
        )
    )

    ## Upload second image.
    if tweet_page_path:
        input_box.send_keys(tweet_page_path)

        ## Wait for the second image to be uploaded and processed.
        WebDriverWait(browser, 30).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div[data-testid='attachments']")
            )
        )

    ## Add tweet.
    tweet_box = WebDriverWait(browser, 30).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//div[@contenteditable='true' and @data-testid='tweetTextarea_0']",
            )
        )
    )
    tweet_box.send_keys(tweet_content.replace("\n", Keys.RETURN))

    ## Add a secondary follow-up tweet.
    if post_tweet:
        tweet_reply_btn = WebDriverWait(browser, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[data-testid="addButton"]'))
        )
        tweet_reply_btn.click()

        ## Add post-tweet.
        tweet_box = WebDriverWait(browser, 30).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//div[@contenteditable='true' and @data-testid='tweetTextarea_1']",
                )
            )
        )
        tweet_box.send_keys(post_tweet.replace("\n", Keys.RETURN))

    button = WebDriverWait(browser, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "div[data-testid='tweetButton']"))
    )
    button.click()

    # Wait for the tweet to be sent.
    # confirmation_message = WebDriverWait(browser, 30).until(
    #     EC.presence_of_element_located(
    #         (By.XPATH, "//span[contains(text(), 'Your post were sent.')]")
    #     )
    # )

    print("Tweet sent successfully.")
    browser.quit()
    return True


def main():
    """Generate a weekly review of highlights and takeaways from papers."""
    vs.validate_openai_env()
    is_review = True

    ## Define arxiv code.
    arxiv_codes = db.get_arxiv_id_list(db.db_params, "summary_notes")
    done_codes = db.get_arxiv_id_list(db.db_params, "tweet_reviews")
    arxiv_codes = list(set(arxiv_codes) - set(done_codes))
    arxiv_codes = sorted(arxiv_codes)[-10:]
    arxiv_code = random.choice(arxiv_codes)

    last_post = db.get_latest_tstp(
        db.db_params, "tweet_reviews", extra_condition="where is_daily_review=true"
    )
    if datetime.datetime.date(last_post) == datetime.datetime.today().date():
        is_review = False

    ## Load previous tweets.
    n_tweets = 5
    with open(f"{DATA_PATH}/tweets.json", "r") as f:
        tweets = json.load(f)
    previous_tweets = "\n----------\n".join(
        [
            f"[{k}] {v}"
            for i, (k, v) in enumerate(tweets.items())
            if i > len(tweets) - n_tweets
        ]
    )

    paper_summary = db.get_extended_notes(arxiv_code, expected_tokens=6000)
    paper_details = db.load_arxiv(arxiv_code)
    publish_date = paper_details["published"][0].strftime("%B %Y")
    title_map = db.get_arxiv_title_dict()
    paper_title = title_map[arxiv_code]

    tweet_facts = (
        """```
    **Title: """
        + paper_title
        + """**"""
        + paper_summary
        + "```"
    )
    post_tweet = f"read more on the LLMpedia: https://llmpedia.streamlit.app/?arxiv_code={arxiv_code}"

    ## Run model.
    tweet = vs.write_tweet(
        previous_tweets=previous_tweets,
        tweet_facts=tweet_facts,
        is_review=is_review,
        model="claude-sonnet",
    )
    print("Generated tweet: ")
    print(tweet)

    edited_tweet = vs.edit_tweet(tweet, is_review, model="claude-opus")
    edited_tweet = bold(edited_tweet, publish_date)

    print("Edited tweet: ")
    print(edited_tweet)

    ## Send tweet to API.
    tweet_image_path = f"{IMG_PATH}/{arxiv_code}.png"
    tweet_page_path = None
    if is_review:
        tweet_page_path = f"{PAGE_PATH}/{arxiv_code}.png"

    send_tweet(edited_tweet, tweet_image_path, tweet_page_path, post_tweet)

    ## Store.
    db.insert_tweet_review(arxiv_code, edited_tweet, datetime.datetime.now(), is_review)


if __name__ == "__main__":
    main()
