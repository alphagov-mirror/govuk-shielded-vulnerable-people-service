from flask import abort, current_app, redirect, request, session

from .blueprint import form
from .shared.routing import get_redirect_to_terminal_page
from .shared.session import load_answers_into_session_if_available, set_form_answers_from_nhs_user_info


@form.route("/nhs-login-callback", methods=["GET"])
def get_nhs_login_callback():
    session.permanent = True

    if "error" in request.args:
        error_description = request.args.get('error_description')
        if error_description == "ConsentNotGiven":
            return redirect("no-consent")
        else:
            abort(500)

    nhs_user_info = current_app.nhs_oidc_client.get_nhs_user_info_from_authorization_callback(request.args)

    session["nhs_sub"] = nhs_user_info["sub"]

    if load_answers_into_session_if_available():
        return get_redirect_to_terminal_page()

    set_form_answers_from_nhs_user_info(nhs_user_info)

    return redirect("postcode-eligibility")


@form.route("/start", methods=["GET"])
def get_start():
    session.clear()
    return redirect("/applying-on-own-behalf")


@form.route("/", methods=["GET"])
def get_default_route():
    session.clear()
    return redirect("/applying-on-own-behalf")
