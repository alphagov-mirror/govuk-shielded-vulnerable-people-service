import datetime
import enum
import email
import json
import jsonschema
import os
import phonenumbers

import stdnum
import stdnum.gb.nhs

import re

from flask import (
    current_app,
    Blueprint,
    render_template,
    redirect,
    request,
    session,
)


from . import postcode_lookup_helper, form_response_model

form = Blueprint("form", __name__)

PAGE_TITLES = {
    "privacy": "Privacy",
    "accessibility": "Accessibility statement",
    "cookies": "Cookies",
    "address-lookup": "Select your address",
    "basic-care-needs": "Are your basic care needs being met at the moment?",
    "carry-supplies": "Is there someone in the house who’s able to carry a delivery of supplies inside?	",
    "check-contact-details": "Check this is correct",
    "check-your-answers": "Are you ready to send your application?",
    "contact-details": "What are your contact details?",
    "date-of-birth": "What is your date of birth?",
    "dietary-requirements": "Do you have any special dietary requirements?",
    "essential-supplies": "Do you have a way of getting essential supplies delivered at the moment?",
    "live-in-england": "Do you live in England?",
    "medical-conditions": "Do you have one of the listed medical conditions?",
    "name": "What is your name?	",
    "nhs-letter": "Have you had a letter from the NHS or been told by your doctor to ’shield’ because you’re clinically extremely vulnerable to coronavirus?",
    "nhs-number": "Do you know your NHS number?",
    "not-eligible-england": "Sorry, this service is only available in England",
    "not-eligible-medical": "Sorry, you’re not eligible for help through this service",
    "postcode-lookup": "What is the postcode where you need support?",
    "confirmation": "Registration complete",
    "support-address": "What is the address where you need support?",
}


def blank_form_sections(*sections_to_blank):
    session["form_answers"] = {
        section: {**answers} if isinstance(answers, dict) else answers
        for section, answers in session.get("form_answers", {}).items()
        if section not in sections_to_blank
    }


def redirect_to_next_form_page(redirect_target=True):
    next_page_has_answer = (
        form_answers().get(redirect_target.strip("/").replace("-", "_")) is not None
    )
    print(next_page_has_answer)
    if session.get("check_answers_page_seen") and next_page_has_answer:
        return redirect("/check-your-answers")

    return redirect(redirect_target)


def route_to_next_form_page():
    current_form = request.url_rule.rule.strip("/")
    answer = form_answers().get(current_form.replace("-", "_"))

    if current_form == "address-lookup":
        return redirect("/support-address")
    elif current_form == "applying-on-own-behalf":
        applying_on_own_behalf = request_form()["applying_on_own_behalf"]
        if (
            ApplyingOnOwnBehalfAnswers(applying_on_own_behalf)
            is ApplyingOnOwnBehalfAnswers.YES
        ):
            return redirect_to_next_form_page("/nhs-login")
        return redirect_to_next_form_page("/live-in-england")
    elif current_form == "basic-care-needs":
        return redirect_to_next_form_page("/check-your-answers")
    elif current_form == "carry-supplies":
        return redirect_to_next_form_page("/basic-care-needs")
    elif current_form == "check-contact-details":
        return redirect_to_next_form_page("/nhs-number")
    elif current_form == "contact-details":
        return redirect_to_next_form_page("/check-contact-details")
    elif current_form == "date-of-birth":
        return redirect_to_next_form_page("/postcode-lookup")
    elif current_form == "dietary-requirements":
        return redirect_to_next_form_page("/carry-supplies")
    elif current_form == "essential-supplies":
        essential_supplies = request_form()["essential_supplies"]
        if YesNoAnswers(essential_supplies) is YesNoAnswers.YES:
            blank_form_sections("dietary_requirements", "carry_supplies")
            return redirect_to_next_form_page("/basic-care-needs")
        return redirect_to_next_form_page("/dietary-requirements")
    elif current_form == "live-in-england":
        if YesNoAnswers(answer) is YesNoAnswers.YES:
            return redirect_to_next_form_page("/nhs-letter")
        return redirect("/not-eligible-england")
    elif current_form == "medical-conditions":
        if MedicalConditionsAnswers(answer) is MedicalConditionsAnswers.YES:
            return redirect_to_next_form_page("/name")
        return redirect("/not-eligible-medical")
    elif current_form == "name":
        return redirect_to_next_form_page("/date-of-birth")
    elif current_form == "nhs-letter":
        if NHSLetterAnswers(answer) is NHSLetterAnswers.YES:
            blank_form_sections("medical_conditions")
            return redirect_to_next_form_page("/name")
        return redirect_to_next_form_page("/medical-conditions")
    elif current_form == "nhs-number":
        return redirect_to_next_form_page("/essential-supplies")
    elif current_form == "postcode-lookup":
        return redirect("/address-lookup")
    elif current_form == "support-address":
        return redirect_to_next_form_page("/contact-details")
    else:
        raise RuntimeError("An unexpected error occurred")


def render_template_with_title(template_name, *args, **kwargs):
    if not template_name.endswith(".html"):
        raise ValueError(
            "Template names must end with '.html' for a title to be assigned"
        )
    return render_template(
        template_name, *args, title_text=PAGE_TITLES[template_name[:-5]], **kwargs
    )


def update_session_answers_from_form():
    session["form_answers"] = {
        **session.setdefault("form_answers",),
        **request_form(),
    }
    session["error_items"] = {}


def form_answers():
    return session.setdefault("form_answers", {})


def get_radio_options_from_enum(target_enum, selected_value):
    return [
        {
            "value": value.value,
            "text": value.value,
            "checked": selected_value == value.value,
        }
        for value in target_enum
    ]


@enum.unique
class YesNoAnswers(enum.Enum):
    YES = "Yes"
    NO = "No"


def get_errors_from_session(error_group_name):
    error_list = []
    error_messages = {}
    if session.get("error_items") and session["error_items"].get(error_group_name):
        errors = session["error_items"][error_group_name]
        error_messages = {k: {"text": v} for k, v in errors.items()}
        error_list = [
            {"text": text, "href": f"#{field}"} for field, text in errors.items()
        ]
    answers = session.setdefault("form_answers", {})
    return {
        "error_list": error_list,
        "error_messages": error_messages,
        "answers": answers,
    }


def validate_radio_button(EnumClass, value_key, error_message):
    value = request_form().get(value_key)
    try:
        EnumClass(value)
    except ValueError:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            value_key: {value_key: error_message},
        }
        return False
    if session.get("error_items"):
        session["error_items"].pop(value_key)
    return True


def validate_live_in_england():
    return validate_radio_button(
        YesNoAnswers, "live_in_england", "Select yes if you live in England"
    )


@enum.unique
class ApplyingOnOwnBehalfAnswers(enum.Enum):
    YES = "Yes, I'm applying on my own behalf."
    NO = "No, I'm applying on behalf of someone else."


@form.route("/applying-on-own-behalf", methods=["GET"])
def get_apply_on_own_behalf():
    return render_template_with_title(
        "applying-on-own-behalf.html",
        radio_items=get_radio_options_from_enum(
            ApplyingOnOwnBehalfAnswers, form_answers().get("applying_on_own_behalf")
        ),
        previous_path="/",
        **get_errors_from_session("applying_on_own_behalf"),
    )


def validate_applying_on_own_behalf():
    return validate_radio_button(
        ApplyingOnOwnBehalfAnswers,
        "applying_on_own_behalf",
        "Select yes if you are applying on your own behalf",
    )


@form.route("/applying-on-own-behalf", methods=["POST"])
def post_applying_on_own_behalf():
    if not validate_applying_on_own_behalf():
        return redirect("/applying-on-own-behalf")
    update_session_answers_from_form()
    return route_to_next_form_page()


@form.route("/start", methods=["GET"])
def get_start():
    return redirect("/live-in-england")


@form.route("/live-in-england", methods=["GET"])
def get_live_in_england():
    return render_template_with_title(
        "live-in-england.html",
        radio_items=get_radio_options_from_enum(
            YesNoAnswers, form_answers().get("live_in_england")
        ),
        previous_path="/applying-on-own-behalf",
        **get_errors_from_session("live_in_england"),
    )


@form.route("/live-in-england", methods=["POST"])
def post_live_in_england():
    if not validate_live_in_england():
        return redirect("/live-in-england")
    update_session_answers_from_form()
    return route_to_next_form_page()


@enum.unique
class NHSLetterAnswers(enum.Enum):
    YES = "Yes, I’ve been told to shield"
    NO = "No, I haven’t been told to shield"
    NOT_SURE = "Not sure"


def validate_nhs_letter():
    return validate_radio_button(
        NHSLetterAnswers, "nhs_letter", "Select if you received the letter from the NHS"
    )


@form.route("/nhs-letter", methods=["POST"])
def post_nhs_letter():
    if not validate_nhs_letter():
        return redirect("/nhs-letter")
    update_session_answers_from_form()
    return route_to_next_form_page()


@form.route("/nhs-letter", methods=["GET"])
def get_nhs_letter():
    return render_template_with_title(
        "nhs-letter.html",
        radio_items=get_radio_options_from_enum(
            NHSLetterAnswers, form_answers().get("nhs_letter")
        ),
        previous_path="/live-in-england",
        **get_errors_from_session("nhs_letter"),
    )


@enum.unique
class MedicalConditionsAnswers(enum.Enum):
    YES = "Yes, I have one of the listed medical conditions"
    NO = "No, I do not have one of the listed medical conditions"


def validate_medical_conditions():
    return validate_radio_button(
        MedicalConditionsAnswers,
        "medical_conditions",
        "Select yes if you have one of the medical conditions on the list",
    )


@form.route("/medical-conditions", methods=["POST"])
def post_medical_conditions():
    if not validate_medical_conditions():
        return redirect("/medical-conditions")

    update_session_answers_from_form()
    return route_to_next_form_page()


@form.route("/medical-conditions", methods=["GET"])
def get_medical_conditions():
    return render_template_with_title(
        "medical-conditions.html",
        radio_items=get_radio_options_from_enum(
            MedicalConditionsAnswers, form_answers().get("medical_conditions")
        ),
        previous_path="/nhs-letter",
        **get_errors_from_session("medical_conditions"),
    )


def validate_mandatory_form_field(section_key, value_key, error_message):
    if not request_form().get(value_key):
        existing_section = session.setdefault("error_items", {}).setdefault(
            section_key, {}
        )
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            section_key: {**existing_section, value_key: error_message},
        }
        return False
    return True


def validate_name():
    return all(
        [
            validate_mandatory_form_field(
                "name", "first_name", "Enter your first name"
            ),
            validate_mandatory_form_field("name", "last_name", "Enter your last name"),
        ]
    )


def request_form():
    return {k: v for k, v in request.form.items() if k != "csrf_token"}


@form.route("/name", methods=["POST"])
def post_name():
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        "name": {**request_form()},
    }
    if not validate_name():
        return redirect("/name")

    session["error_items"] = {}
    return route_to_next_form_page()


@form.route("/name", methods=["GET"])
def get_name():
    return render_template_with_title(
        "name.html",
        values=form_answers().get("name", {}),
        previous_path="/medical-conditions"
        if session.get("medical_conditions")
        else "/nhs-letter",
        **get_errors_from_session("name"),
    )


def isNumber(string):
    try:
        int(string)
        return True
    except ValueError:
        return False


def isPositiveInt(string):
    try:
        value = int(string)
    except ValueError:
        return False
    return value == float(string) and value > 0


def failing_field(field_bools, field_names):
    return field_names[field_bools.index(True)]


def validate_date_of_birth():
    day = request_form().get("day", "")
    month = request_form().get("month", "")
    year = request_form().get("year", "")

    fields = [month, day, year]
    fieldsEmpty = [period == "" for period in fields]
    fieldsNotNumbers = [not isNumber(period) for period in fields]
    fieldsNotPositiveInt = [not isPositiveInt(period) for period in fields]
    fieldNames = ("month", "day", "year")

    error = None
    if all(fieldsEmpty):
        error = "Enter your date of birth"
    elif any(fieldsEmpty):
        error = "Enter your date of birth and include a day month and a year"
    elif any(fieldsNotNumbers):
        error = f"Enter {failing_field(fieldsNotNumbers, fieldNames)} as a number"
    elif any(fieldsNotPositiveInt):
        error = f"Enter a real {failing_field(fieldsNotPositiveInt, fieldNames)}"

    invalid_date_message = "Enter a real date of birth"
    if error is None:
        try:
            date = datetime.date(int(year), int(day), int(month))
        except ValueError:
            error = invalid_date_message
    if error is None:
        if (date - datetime.date.today()).days > 0:
            error = "Date of birth must be in the past"
        elif (datetime.date.today() - date).days / 365.25 > 150:
            error = invalid_date_message

    session["error_items"] = {
        **session.setdefault("error_items", {}),
        "date_of_birth": {"date_of_birth": error},
    }

    return error is None


@form.route("/date-of-birth", methods=["POST"])
def post_date_of_birth():
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        "date_of_birth": {**request_form()},
    }
    if not validate_date_of_birth():
        return redirect("/date-of-birth")

    session["error_items"] = {}
    return route_to_next_form_page()


@form.route("/date-of-birth", methods=["GET"])
def get_date_of_birth():
    return render_template_with_title(
        "date-of-birth.html",
        previous_path="/name",
        values=form_answers().get("date_of_birth", {}),
        **get_errors_from_session("date_of_birth"),
    )


def validate_postcode(section):
    postcode = session.get("postcode")

    postcode.replace(" ", "")
    postcode_regex = "(([A-Z]{1,2}[0-9][A-Z0-9]?|ASCN|STHL|TDCU|BBND|[BFS]IQQ|PCRN|TKCA) ?[0-9][A-Z]{2}|BFPO ?[0-9]{1,4}|(KY[0-9]|MSR|VG|AI)[ -]?[0-9]{4}|[A-Z]{2} ?[0-9]{2}|GE ?CX|GIR ?0A{2}|SAN ?TA1)"
    error = None
    if not postcode:
        error = "What is the postcode where you need support?"
    elif re.match(postcode_regex, postcode) is None:
        error = "Enter a real postcode"

    if error:
        error_section = session.setdefault("error_items", {}).get(section, {})
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            section: {**error_section, "postcode": error},
        }

    return error is None


@form.route("/address-lookup", methods=["POST"])
def post_address_lookup():
    if not validate_mandatory_form_field(
        "address_lookup", "address", "An address must be selected"
    ):
        return redirect("/address-lookup")
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        "support_address": {**json.loads(request_form()["address"])},
    }
    session["error_items"] = {}
    return route_to_next_form_page()


@form.route("/address-lookup", methods=["GET"])
def get_address_lookup():
    postcode = session["postcode"]
    try:
        addresses = postcode_lookup_helper.get_addresses_from_postcode(postcode)
    except postcode_lookup_helper.PostcodeNotFound:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            "support_address": {"postcode", "Could not find postcode"},
        }
        redirect("/postcode-lookup")
    except postcode_lookup_helper.NoAddressesFoundAtPostcode:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            "support_address": {
                "support_address",
                f"No addresses found for {postcode}",
            },
        }
        redirect("/support-address")
    except postcode_lookup_helper.ErrorFindingAddress:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            "support_address": {
                "support_address",
                "An error has occurred, please enter your address manually",
            },
        }
        redirect("/support-address")

    return render_template_with_title(
        "address-lookup.html",
        previous_path="/postcode-lookup",
        postcode=postcode,
        addresses=addresses,
        **get_errors_from_session("postcode"),
    )


@form.route("/postcode-lookup", methods=["POST"])
def post_postcode_lookup():
    session["postcode"] = request_form().get("postcode")
    if not validate_postcode("postcode"):
        return redirect("/postcode-lookup")

    session["error_items"] = {}
    return route_to_next_form_page()


@form.route("/postcode-lookup", methods=["GET"])
def get_postcode_lookup():
    return render_template_with_title(
        "postcode-lookup.html",
        previous_path="/date-of-birth",
        values={"postcode": session.get("postcode", "")},
        **get_errors_from_session("postcode"),
    )


def validate_support_address():
    value = all(
        [
            validate_mandatory_form_field(
                "support_address",
                "building_and_street_line_1",
                "Enter a building and street",
            ),
            validate_mandatory_form_field(
                "support_address", "town_city", "Enter a town or city"
            ),
            validate_postcode("support_address"),
        ]
    )
    return value


@form.route("/support-address", methods=["POST"])
def post_support_address():
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        "support_address": {**request_form()},
    }
    session["error_items"] = {}
    if not validate_support_address():
        return redirect("/support-address")
    return route_to_next_form_page()


@form.route("/support-address", methods=["GET"])
def get_support_address():
    return render_template_with_title(
        "support-address.html",
        previous_path="/address-lookup",
        values=form_answers().get("support_address", {}),
        **get_errors_from_session("support_address"),
    )


def format_phone_number_if_valid(phone_number):
    try:
        return phonenumbers.format_number(
            phonenumbers.parse(phone_number, region="GB"),
            phonenumbers.PhoneNumberFormat.NATIONAL,
        )
    except phonenumbers.NumberParseException:
        return phone_number


def validate_phone_number_if_present(section_key, phone_number_key):
    try:
        phone_number = request_form().get(phone_number_key, "")
        if phone_number:
            phonenumbers.parse(phone_number, region="GB")
    except phonenumbers.NumberParseException:
        error_message = (
            "Enter a telephone number, like 020 7946 0000, 07700900000 or +44 0808 157 0192",
        )
        error_section = session.setdefault("error_items", {}).get(section_key, {})
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            section_key: {**error_section, phone_number_key: error_message},
        }
        return False
    return True


def validate_email_if_present(section_key, email_key):
    email_address = request_form().get(email_key)
    email_regex = r"([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})"
    if email_address and re.match(email_regex, email_address) is None:
        error_message = (
            "Enter email address in the correct format, like name@example.com"
        )
        error_section = session.setdefault("error_items", {}).get(section_key, {})
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            section_key: {**error_section, email_key: error_message},
        }
        return False
    return True


def validate_contact_details(section_key):
    value = all(
        [
            validate_email_if_present(section_key, "email"),
            validate_phone_number_if_present(section_key, "phone_number_calls"),
            validate_phone_number_if_present(section_key, "phone_number_texts"),
        ]
    )
    return value


@form.route("/contact-details", methods=["POST"])
def post_contact_details():
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        "contact_details": {
            **request_form(),
            **{
                phone_key: format_phone_number_if_valid(request_form().get(phone_key))
                for phone_key in ("phone_number_calls", "phone_number_texts")
            },
        },
    }
    session["error_items"] = {}
    if not validate_contact_details("contact_details"):
        return redirect("/contact-details")
    return route_to_next_form_page()


@form.route("/contact-details", methods=["GET"])
def get_contact_details():
    return render_template_with_title(
        "contact-details.html",
        previous_path="/name",
        values=form_answers().get("contact_details", {}),
        **get_errors_from_session("contact_details"),
    )


@form.route("/check-contact-details", methods=["POST"])
def post_check_contact_details():
    existing_answers = form_answers().get("contact_details", {})
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        "contact_details": {**existing_answers, **request_form(),},
    }
    session["error_items"] = {}
    if not validate_contact_details("check_contact_details"):
        return redirect("/check-contact-details")

    return route_to_next_form_page()


@form.route("/check-contact-details", methods=["GET"])
def get_check_contact_details():
    return render_template_with_title(
        "check-contact-details.html",
        previous_path="/contact-details",
        values=form_answers().get("contact_details", {}),
        button_text="These details are correct",
        **get_errors_from_session("check_contact_details"),
    )


def validate_nhs_number():
    error = None
    nhs_number = request_form().get("nhs_number")
    if nhs_number:
        try:
            stdnum.gb.nhs.validate(nhs_number)
        except stdnum.exceptions.InvalidLength:
            error = "Enter your 10-digit NHS number"
        except (
            stdnum.exceptions.InvalidChecksum,
            stdnum.exceptions.InvalidComponent,
            stdnum.exceptions.InvalidFormat,
        ):
            error = "Enter a real NHS number"
    else:
        error = "Enter your 10-digit NHS number"

    if error is not None:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            "nhs_number": {"nhs_number": error},
        }
    return error is None


@form.route("/nhs-number", methods=["POST"])
def post_nhs_number():
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        **request_form(),
        "know_nhs_number": "Yes, I know my NHS number",
    }
    session["error_items"] = {}
    if not validate_nhs_number():
        return redirect("/nhs-number")

    return route_to_next_form_page()


@form.route("/nhs-number", methods=["GET"])
def get_nhs_number():
    return render_template_with_title(
        "nhs-number.html",
        previous_path="/contact-details",
        values={"nhs_number": form_answers().get("nhs_number", "")},
        **get_errors_from_session("nhs_number"),
    )


def validate_essential_supplies():
    return validate_radio_button(
        YesNoAnswers,
        "essential_supplies",
        "Select yes if you have a way of getting essential supplies delivered at the moment",
    )


@form.route("/essential-supplies", methods=["GET"])
def get_essential_supplies():
    return render_template_with_title(
        "essential-supplies.html",
        radio_items=get_radio_options_from_enum(
            YesNoAnswers, form_answers().get("essential_supplies")
        ),
        previous_path="/nhs-number",
        **get_errors_from_session("essential_supplies"),
    )


@form.route("/essential-supplies", methods=["POST"])
def post_essential_supplies():
    if not validate_essential_supplies():
        return redirect("/essential-supplies")
    update_session_answers_from_form()
    return route_to_next_form_page()


def validate_basic_care_needs():
    return validate_radio_button(
        YesNoAnswers,
        "basic_care_needs",
        "Select yes if your basic care needs are being met at the moment",
    )


@form.route("/basic-care-needs", methods=["GET"])
def get_basic_care_needs():
    did_supplies_questions = (
        YesNoAnswers(form_answers().get("essential_supplies")) is YesNoAnswers.NO
    )
    previous_path = (
        "/carry-supplies" if did_supplies_questions else "/essential-supplies"
    )
    return render_template_with_title(
        "basic-care-needs.html",
        previous_path=previous_path,
        radio_items=get_radio_options_from_enum(
            YesNoAnswers, form_answers().get("basic_care_needs")
        ),
        **get_errors_from_session("basic_care_needs"),
    )


@form.route("/basic-care-needs", methods=["POST"])
def post_basic_care_needs():
    if not validate_basic_care_needs():
        return redirect("/basic-care-needs")
    update_session_answers_from_form()
    return route_to_next_form_page()


def validate_dietary_requirements():
    return validate_radio_button(
        YesNoAnswers,
        "dietary_requirements",
        "Select yes if you have special dietary requirements",
    )


@form.route("/dietary-requirements", methods=["GET"])
def get_dietary_requirements():
    return render_template_with_title(
        "dietary-requirements.html",
        radio_items=get_radio_options_from_enum(
            YesNoAnswers, form_answers().get("dietary_requirements")
        ),
        previous_path="/essential-supplies",
        **get_errors_from_session("dietary_requirements"),
    )


@form.route("/dietary-requirements", methods=["POST"])
def post_dietary_requirements():
    if not validate_dietary_requirements():
        return redirect("/dietary-requirements")
    update_session_answers_from_form()
    return route_to_next_form_page()


def validate_carry_supplies():
    return validate_radio_button(
        YesNoAnswers,
        "carry_supplies",
        "Select yes if there’s someone in the house who’s able to carry a delivery of supplies inside",
    )


@form.route("/carry-supplies", methods=["GET"])
def get_carry_supplies():
    return render_template_with_title(
        "carry-supplies.html",
        radio_items=get_radio_options_from_enum(
            YesNoAnswers, form_answers().get("carry_supplies")
        ),
        previous_path="/dietary-requirements",
        **get_errors_from_session("carry_supplies"),
    )


@form.route("/carry-supplies", methods=["POST"])
def post_carry_supplies():
    if not validate_carry_supplies():
        return redirect("/carry-supplies")
    update_session_answers_from_form()
    return route_to_next_form_page()


def _slice(keys, _dict):
    return (_dict[key] for key in keys if _dict[key])


def get_summary_rows_from_form_answers():
    summary_rows = []
    answers = form_answers()
    order = [
        "applying_on_own_behalf",
        "live_in_england",
        "nhs_letter",
        "medical_conditions",
        "name",
        "date_of_birth",
        "support_address",
        "contact_details",
        "nhs_number",
        "essential_supplies",
        "dietary_requirements",
        "carry_supplies",
        "basic_care_needs",
    ]

    for key in order:
        if key not in answers:
            continue

        answer = answers[key]
        dashed_key = key.replace("_", "-")
        question = PAGE_TITLES[dashed_key]

        value = {}
        row = {
            "key": {"text": question, "classes": "govuk-!-width-two-thirds",},
            "value": {},
            "actions": {
                "items": [
                    {
                        "href": f"/{dashed_key}",
                        "text": "Change",
                        "visuallyHiddenText": question,
                    }
                ]
            },
        }
        if key == "support_address":
            value["html"] = "<br>".join(
                _slice(
                    [
                        "building_and_street_line_1",
                        "building_and_street_line_2",
                        "town_city",
                        "county",
                        "postcode",
                    ],
                    answer,
                )
            )
        elif key == "name":
            value["text"] = " ".join(
                _slice(["first_name", "middle_name", "last_name"], answer)
            )
        elif key == "contact_details":
            value["html"] = "<br>".join(
                [
                    f"Phone number: {answer['phone_number_calls']}",
                    f"Text: {answer['phone_number_texts']}",
                    f"Email: {answer['email']}",
                ]
            )
        elif key == "date_of_birth":
            value["text"] = "{day:02}/{month:02}/{year}".format(
                **{k: int(v) for k, v in answer.items()}
            )
        else:
            value["text"] = answers[key]

        row["value"] = value
        summary_rows.append(row)

    return summary_rows


@form.route("/check-your-answers", methods=["GET"])
def get_check_your_answers():
    session["check_answers_page_seen"] = True
    return render_template_with_title(
        "check-your-answers.html",
        previous_path="/basic-care-needs",
        summary_rows=get_summary_rows_from_form_answers(),
    )


@form.route("/check-your-answers", methods=["POST"])
def post_check_your_answers():
    answers = form_answers()
    with open(os.path.join(current_app.root_path, "answers_schema.json")) as fh:
        schema = json.load(fh)
    try:
        jsonschema.validate(instance=answers, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        #TODO Add govuk.notify call here
        current_app.logger.exception("JSON Schema validation error in form answers", e)
    form_response_model.write_answers_to_table(form_answers())
    return redirect("/confirmation",)


@form.route("/confirmation", methods=["GET"])
def get_confirmation():
    return render_template_with_title(
        "confirmation.html",
        contact_gp=NHSLetterAnswers(form_answers()["nhs_letter"])
        is NHSLetterAnswers.YES,
    )


@form.route("/privacy", methods=["GET"])
def get_privacy():
    return render_template_with_title("privacy.html")


@form.route("/accessibility", methods=["GET"])
def get_accessibility():
    return render_template_with_title("accessibility.html")


def redirect_url(default="/"):
    return request.args.get("next") or request.referrer or default


@form.route("/cookies", methods=["GET"])
def get_cookies():
    return render_template_with_title("cookies.html", back_url=redirect_url())


@form.route("/not-eligible-medical", methods=["GET"])
def get_not_eligible_medical():
    return render_template_with_title(
        "not-eligible-medical.html", back_url=redirect_url()
    )


@form.route("/not-eligible-england", methods=["GET"])
def get_not_eligible_england():
    update_session_answers_from_form()
    return render_template_with_title(
        "not-eligible-england.html", back_url=redirect_url()
    )
