SECRET_KEY = "wagtail-block-ids-tests"
DEBUG = False
ALLOWED_HOSTS = ["localhost", "testserver"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "taggit",
    "wagtail",
    "wagtail.images",
    "wagtail.documents",
    "wagtail.admin",
    "wagtail.users",
    "wagtail.search",
    "wagtail.sites",
    "testapp",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "testapp.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
STATIC_URL = "/static/"
WAGTAIL_SITE_NAME = "Wagtail Block IDs tests"
WAGTAILADMIN_BASE_URL = "http://localhost"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"


class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
