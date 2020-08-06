from flask import redirect

from .shared.answers_enums import YesNoAnswers, get_radio_options_from_enum
from .blueprint import form
from .shared.render import render_template_with_title
from .shared.routing import route_to_next_form_page
from .shared.session import (
    form_answers,
    get_errors_from_session,
    request_form,
    update_session_answers_from_form,
)
from .shared.validation import validate_basic_care_needs


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
    update_session_answers_from_form()
    if not validate_basic_care_needs():
        return redirect("/basic-care-needs")
    return route_to_next_form_page()
