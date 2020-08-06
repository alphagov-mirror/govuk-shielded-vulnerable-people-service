import datetime
import json
import os
import re

import jsonschema
import phonenumbers
import stdnum.gb.nhs
from flask import current_app, session

from .answers_enums import (
    ApplyingOnOwnBehalfAnswers,
    MedicalConditionsAnswers,
    NHSLetterAnswers,
    ViewOrSetupAnswers,
    YesNoAnswers,
)
from .session import form_answers, get_answer_from_form, request_form


def validate_mandatory_form_field(section_key, value_key, error_message):
    if not form_answers().get(section_key, {}).get(value_key):
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


def validate_view_or_setup():
    value = request_form().get("view_or_setup")
    try:
        ViewOrSetupAnswers(value)
    except ValueError:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            "view_or_setup": {
                "view_or_setup": "You must select if you would like to set up an account, or access an account via your NHS Login."
            },
        }
        return False
    if session.get("error_items"):
        session["error_items"].pop("view_or_setup")
    return True


def validate_applying_on_own_behalf():
    return validate_radio_button(
        ApplyingOnOwnBehalfAnswers,
        "applying_on_own_behalf",
        "Select yes if you are applying on your own behalf",
    )


def validate_radio_button(EnumClass, value_key, error_message):
    value = form_answers().get(value_key)
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


def validate_nhs_letter():
    return validate_radio_button(
        NHSLetterAnswers, "nhs_letter", "Select if you received the letter from the NHS"
    )


def validate_live_in_england():
    return validate_radio_button(
        YesNoAnswers, "live_in_england", "Select yes if you live in England"
    )


def validate_nhs_login():
    return validate_radio_button(
        YesNoAnswers, "nhs_login", "Select yes if you want log in with you NHS details",
    )


def validate_register_with_nhs():
    value = request_form().get("nhs_registration")
    try:
        YesNoAnswers(value)
    except ValueError:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            "nhs_registration": {
                "nhs_registration": "You need to select if you want to register an account with the NHS in order to retrieve your answers at a alater point."
            },
        }
        return False
    if session.get("error_items"):
        session["error_items"].pop("nhs_registration")
    return True


def validate_medical_conditions():
    return validate_radio_button(
        MedicalConditionsAnswers,
        "medical_conditions",
        "Select yes if you have one of the medical conditions on the list",
    )


def validate_address_lookup():
    if not request_form().get("address"):
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            "address_lookup": {"address": "You must select an address",},
        }
        return False
    return True


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
    day = form_answers().get("date_of_birth", {}).get("day", "")
    month = form_answers().get("date_of_birth", {}).get("month", "")
    year = form_answers().get("date_of_birth", {}).get("year", "")

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
            date = datetime.date(int(year), int(month), int(day))
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


def validate_postcode(section):
    postcode = session.get("postcode")

    postcode.replace(" ", "")
    postcode_regex = "(([A-Z]{1,2}[0-9][A-Z0-9]?|ASCN|STHL|TDCU|BBND|[BFS]IQQ|PCRN|TKCA) ?[0-9][A-Z]{2}|BFPO ?[0-9]{1,4}|(KY[0-9]|MSR|VG|AI)[ -]?[0-9]{4}|[A-Z]{2} ?[0-9]{2}|GE ?CX|GIR ?0A{2}|SAN ?TA1)"
    error = None
    if not postcode:
        error = "What is the postcode where you need support?"
    elif re.match(postcode_regex, postcode.upper()) is None:
        error = "Enter a real postcode"

    if error:
        error_section = session.setdefault("error_items", {}).get(section, {})
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            section: {**error_section, "postcode": error},
        }

    return error is None


def validate_length(form_answer_key_list, max_length, error_string):
    if len(get_answer_from_form(form_answer_key_list) or "") > max_length:
        session["error_items"] = {
            **session.setdefault("error_items", {}),
            form_answer_key_list[0]: {
                **session["error_items"].get(form_answer_key_list[0], {}),
                form_answer_key_list[-1]: error_string,
            },
        }
        return False
    return True


def validate_support_address():
    length_fstring = "'{}' cannot be longer than {} characters"
    value = all(
        [
            validate_length(
                ("support_address", "building_and_street_line_1"),
                75,
                length_fstring.format("Address line 1", 75),
            ),
            validate_length(
                ("support_address", "building_and_street_line_2"),
                75,
                length_fstring.format("Address line 2", 75),
            ),
            validate_length(
                ("support_address", "town_city"),
                50,
                length_fstring.format("Town or City", 50),
            ),
            validate_length(
                ("support_address", "county"), 50, length_fstring.format("County", 50)
            ),
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


def validate_phone_number_if_present(section_key, phone_number_key):
    try:
        phone_number = form_answers()["contact_details"].get(phone_number_key, "")
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
    email_address = form_answers()["contact_details"].get(email_key)
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


def validate_nhs_number():
    error = None
    nhs_number = form_answers().get("nhs_number")
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


def validate_essential_supplies():

    return validate_radio_button(
        YesNoAnswers,
        "essential_supplies",
        "Select yes if you have a way of getting essential supplies delivered at the moment",
    )


def validate_basic_care_needs():
    return validate_radio_button(
        YesNoAnswers,
        "basic_care_needs",
        "Select yes if your basic care needs are being met at the moment",
    )


def validate_dietary_requirements():
    return validate_radio_button(
        YesNoAnswers,
        "dietary_requirements",
        "Select yes if you have special dietary requirements",
    )


def validate_carry_supplies():
    return validate_radio_button(
        YesNoAnswers,
        "carry_supplies",
        "Select yes if there’s someone in the house who’s able to carry a delivery of supplies inside",
    )


def try_validating_answers_against_json_schema():
    answers = form_answers()
    with open(os.path.join(current_app.root_path, "answers_schema.json")) as fh:
        schema = json.load(fh)
    try:
        jsonschema.validate(instance=answers, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        # TODO Add govuk.notify call here
        current_app.logger.exception("JSON Schema validation error in form answers", e)
