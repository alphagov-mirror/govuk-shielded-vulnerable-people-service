from flask import current_app, redirect, request, session

from .. import form_response_model
from .answers_enums import (
    ApplyingOnOwnBehalfAnswers,
    MedicalConditionsAnswers,
    NHSLetterAnswers,
    YesNoAnswers,
)
from .session_utils import (
    accessing_saved_answers,
    form_answers,
    is_nhs_login_user,
    request_form,
)
from .validation import validate_contact_details, validate_date_of_birth, validate_name

FORM_PAGE_TO_DATA_CHECK_SECTION_NAME = {
    "address-lookup": "support_address",
    "applying-on-own-behalf": "applying_on_own_behalf",
    "basic-care-needs": "basic_care_needs",
    "carry-supplies": "carry_supplies",
    "check-contact-details": "check_contact_details",
    "check-your-answers": "basic_care_needs",
    "contact-details": "contact_details",
    "date-of-birth": "date_of_birth",
    "dietary-requirements": "dietary_requirements",
    "essential-supplies": "essential_supplies",
    "live-in-england": "live_in_england",
    "medical-conditions": "medical_conditions",
    "name": "name",
    "nhs-letter": "nhs_letter",
    "nhs-login": "nhs_login",
    "nhs-number": "nhs_number",
    "postcode-lookup": "support_address",
    "support-address": "support_address",
}


def blank_form_sections(*sections_to_blank):
    session["form_answers"] = {
        section: {**answers} if isinstance(answers, dict) else answers
        for section, answers in session.get("form_answers", {}).items()
        if section not in sections_to_blank
    }


def get_redirect_to_terminal_page():
    if accessing_saved_answers():
        return redirect("/view-answers")
    return redirect("/check-your-answers")


def get_redirect_to_terminal_page_if_applicable():
    if accessing_saved_answers() or session.get("check_answers_page_seen"):
        return redirect("/view-answers")


def redirect_to_next_form_page(redirect_target=True):
    next_page_name = redirect_target.strip("/")
    next_page_does_not_need_answer = (
        form_answers().get(FORM_PAGE_TO_DATA_CHECK_SECTION_NAME[next_page_name])
        is not None
    )

    if accessing_saved_answers():
        form_response_model.write_answers_to_table(session["nhs_sub"], form_answers())

    maybe_redirect_to_terminal_page = None
    if next_page_does_not_need_answer:
        maybe_redirect_to_terminal_page = get_redirect_to_terminal_page_if_applicable()

    return maybe_redirect_to_terminal_page or redirect(redirect_target)


def clear_errors_after(fn):
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        session["error_items"] = {}
        return result

    return wrapper


@clear_errors_after
def get_next_form_url_after_eligibility_check():
    if is_nhs_login_user() and validate_name():
        return get_next_form_url_after_name()
    else:
        return "/name"


@clear_errors_after
def get_next_form_url_after_name():
    if is_nhs_login_user() and validate_date_of_birth():
        return get_next_form_url_after_date_of_birth()
    else:
        return "/date-of-birth"


@clear_errors_after
def get_next_form_url_after_date_of_birth():
    if is_nhs_login_user() and validate_contact_details("contact_details"):
        return get_next_form_url_after_contact_details()
    else:
        return "/contact-details"


@clear_errors_after
def get_next_form_url_after_contact_details():
    if is_nhs_login_user():
        if validate_contact_details("contact_details"):
            return get_next_form_url_after_check_contact_details()
        else:
            return "/contact-details"
    else:
        return "/check-contact-details"


@clear_errors_after
def get_next_form_url_after_check_contact_details():
    if is_nhs_login_user():
        return "/postcode-lookup"
    else:
        return "/nhs-number"


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
    elif current_form == "nhs-login":
        applying_on_own_behalf = request_form()["nhs_login"]
        if YesNoAnswers(applying_on_own_behalf) is YesNoAnswers.YES:
            return redirect(current_app.nhs_oidc_client.get_authorization_url())
        return redirect_to_next_form_page("/live-in-england")
    elif current_form == "basic-care-needs":
        contact_details = form_answers().get("contact_details", {})
        maybe_redirect_to_terminal_page = get_redirect_to_terminal_page_if_applicable()
        if (
            maybe_redirect_to_terminal_page
            or session.get("nhs_sub")
            or not contact_details.get("phone_number_texts")
            or not contact_details.get("email")
            or form_answers().get("applying_on_own_behalf") is False
        ):
            return get_redirect_to_terminal_page()
        else:
            return redirect("/nhs-registration")
    elif current_form == "carry-supplies":
        return redirect_to_next_form_page("/basic-care-needs")
    elif current_form == "check-contact-details":
        return redirect_to_next_form_page(
            get_next_form_url_after_check_contact_details()
        )
    elif current_form == "contact-details":
        return redirect_to_next_form_page(get_next_form_url_after_contact_details())
    elif current_form == "date-of-birth":
        return redirect_to_next_form_page(get_next_form_url_after_date_of_birth())
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
            return redirect_to_next_form_page(
                get_next_form_url_after_eligibility_check()
            )
        return redirect("/not-eligible-medical")
    elif current_form == "name":
        return redirect_to_next_form_page(get_next_form_url_after_name())
    elif current_form == "nhs-letter":
        if NHSLetterAnswers(answer) is NHSLetterAnswers.YES:
            blank_form_sections("medical_conditions")
            return redirect_to_next_form_page(
                get_next_form_url_after_eligibility_check()
            )
        return redirect_to_next_form_page("/medical-conditions")
    elif current_form == "nhs-number":
        return redirect_to_next_form_page("/postcode-lookup")
    elif current_form == "postcode-lookup":
        return redirect("/address-lookup")
    elif current_form == "support-address":
        return redirect_to_next_form_page("/essential-supplies")
    else:
        raise RuntimeError("An unexpected error occurred")


def dynamic_back_url(default="/"):
    return request.args.get("next") or request.referrer or default
