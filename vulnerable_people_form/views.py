import datetime
import enum

from flask import current_app, Blueprint, render_template, redirect, request, session


form = Blueprint("form", __name__)


def update_session_answers_from_form():
    session["form_answers"] = {**session.setdefault("form_answers", {}), **request.form}


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
class LiveInEnglandAnswers(enum.Enum):
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
    value = request.form.get(value_key)
    try:
        EnumClass(value)
    except ValueError:
        session.setdefault("error_items", {})[value_key] = {value_key: error_message}
        return False
    if session.get("error_items"):
        session["error_items"].pop(value_key)
    return True


def validate_live_in_england():
    return validate_radio_button(
        LiveInEnglandAnswers, "live_in_england", "Select yes if you live in England"
    )


@form.route("/live-in-england", methods=["GET"])
def get_live_in_england():
    return render_template(
        "live-in-england.html",
        radio_items=get_radio_options_from_enum(
            LiveInEnglandAnswers, form_answers().get("live_in_england")
        ),
        **get_errors_from_session("live_in_england"),
    )


@form.route("/live-in-england", methods=["POST"])
def post_live_in_england():
    if not validate_live_in_england():
        return redirect("/live-in-england")
    update_session_answers_from_form()

    live_in_england = request.form["live_in_england"]
    if LiveInEnglandAnswers(live_in_england) is LiveInEnglandAnswers.YES:
        return redirect("/nhs-letter")
    return redirect("/not-eligible-england")


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
    nhs_letter = request.form.get("nhs_letter")
    if NHSLetterAnswers(nhs_letter) is NHSLetterAnswers.YES:
        return redirect("/name")
    return redirect("/medical-conditions")


@form.route("/nhs-letter", methods=["GET"])
def get_nhs_letter():
    return render_template(
        "nhs-letter.html",
        radio_items=get_radio_options_from_enum(
            NHSLetterAnswers, form_answers().get("nhs_letter")
        ),
        previous_path="/" ** get_errors_from_session("nhs_letter"),
    )
