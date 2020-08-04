from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader
from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFProtect
from prometheus_flask_exporter import PrometheusMetrics
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
    integrations=[FlaskIntegration()],
)

from . import views
from . import form_response_model
from . import nhs_openconnect_id


def generate_error_handler(code):
    def handle_error(_):
        return render_template(f"{code}.html"), code

    return handle_error


def create_app(config_filename):
    app = Flask(__name__, static_url_path="/assets", instance_relative_config=True)
    app.config.from_pyfile(config_filename)
    app.jinja_loader = ChoiceLoader(
        [
            PackageLoader("vulnerable_people_form"),
            PrefixLoader(
                {"govuk_frontend_jinja": PackageLoader("govuk_frontend_jinja")}
            ),
        ]
    )

    with app.app_context():
        form_response_model.create_tables_if_not_exist()
    app.register_blueprint(views.form)
    CSRFProtect(app)

    app.nhs_oidc_client = nhs_openconnect_id.NHSOIDCDetails()
    app.nhs_oidc_client.init_app(app)

    app.register_error_handler(404, generate_error_handler(404))
    app.register_error_handler(500, generate_error_handler(500))

    metrics = PrometheusMetrics(app)
    metrics.register_default(
        metrics.counter(
            "by_path_counter",
            "Request count by request paths",
            labels={"path": lambda: request.path},
        ),
        metrics.histogram(
            "requests_by_status_and_path",
            "Request latencies by status and path",
            labels={"status": lambda r: r.status_code, "path": lambda: request.path,},
        ),
    )

    sentry_sdk.init(
        dsn=app.config["SENTRY_DSN"], integrations=[FlaskIntegration()],
    )

    return app
