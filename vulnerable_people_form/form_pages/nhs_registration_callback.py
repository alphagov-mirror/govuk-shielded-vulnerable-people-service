from flask import abort, current_app, redirect, request, session

from vulnerable_people_form.form_pages.shared.routing import get_next_form_url_after_nhs_number
from ..integrations import google_analytics
from .blueprint import form
from .shared.constants import NHS_USER_INFO_TO_FORM_ANSWERS, JourneyProgress
from .shared.session import get_answer_from_form, persist_answers_from_session, set_form_answers_from_nhs_user_info


def log_form_and_nhs_answers_differences(nhs_user_info):
    different_answers = []
    for answers_key, nhs_user_info_key in NHS_USER_INFO_TO_FORM_ANSWERS.items():
        form_value = get_answer_from_form(answers_key)
        nhs_value = (
            nhs_user_info_key(nhs_user_info) if callable(nhs_user_info_key) else nhs_user_info.get(nhs_user_info_key)
        )
        if form_value != nhs_value:
            if answers_key == ("nhs_number",):
                google_analytics.track_nhs_number_and_form_value_differs()
            else:
                different_answers.append(
                    {
                        "key": "/".join(answers_key),
                        "nhs_value": nhs_value,
                        "form_value": form_value,
                    }
                )
    if len(different_answers) > 0:
        google_analytics.track_nhs_userinfo_and_form_answers_differs()


@form.route("/nhs-registration-callback", methods=["GET"])
def get_nhs_registration_callback():
    if "error" in request.args:
        error_description = request.args.get('error_description')
        if error_description == "ConsentNotGiven":
            return redirect("no-consent")
        else:
            abort(500)

    state_from_query_string = request.args.get('state')
    if state_from_query_string:
        last_char_of_state = state_from_query_string[len(state_from_query_string)-1]
        journey_progress = JourneyProgress(int(last_char_of_state))
    else:
        abort(500)

    nhs_user_info = current_app.nhs_oidc_client.get_nhs_user_info_from_registration_callback(request.args)
    log_form_and_nhs_answers_differences(nhs_user_info)
    session["nhs_sub"] = nhs_user_info["sub"]
    session["form_answers"]["nhs_number"] = nhs_user_info["nhs_number"]

    if journey_progress is JourneyProgress.NHS_NUMBER:
        set_form_answers_from_nhs_user_info(nhs_user_info)
        redirect_url = get_next_form_url_after_nhs_number()
    elif journey_progress is JourneyProgress.NHS_REGISTRATION:
        persist_answers_from_session()
        redirect_url = "/confirmation"
    else:
        raise ValueError("Unexpected JourneyProgress value extracted from state: " + last_char_of_state)

    return redirect(redirect_url)
