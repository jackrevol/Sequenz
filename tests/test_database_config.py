from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from sequenz.settings import database_config


def test_database_config_uses_sqlite_when_mysql_is_not_configured():
    config = database_config({"DJANGO_DB_PATH": "/tmp/sequenz-test.sqlite3"})

    assert config == {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path("/tmp/sequenz-test.sqlite3"),
    }


def test_database_config_builds_mysql_connection():
    config = database_config({
        "DB_HOST": "mysql.internal",
        "DB_PORT": "3306",
        "DB_NAME": "sequenz_prod",
        "DB_USER": "sequenz",
        "DB_PASSWORD": "secret",
    })

    assert config["ENGINE"] == "django.db.backends.mysql"
    assert config["HOST"] == "mysql.internal"
    assert config["PORT"] == 3306
    assert config["NAME"] == "sequenz_prod"
    assert config["USER"] == "sequenz"
    assert config["PASSWORD"] == "secret"
    assert config["OPTIONS"]["charset"] == "utf8mb4"


def test_database_config_rejects_partial_mysql_configuration():
    with pytest.raises(ImproperlyConfigured, match="DB_PORT, DB_NAME, DB_USER, DB_PASSWORD"):
        database_config({"DB_HOST": "mysql.internal"})


def test_database_config_rejects_non_numeric_port():
    with pytest.raises(ImproperlyConfigured, match="DB_PORT must be an integer"):
        database_config({
            "DB_HOST": "mysql.internal",
            "DB_PORT": "mysql",
            "DB_NAME": "sequenz_prod",
            "DB_USER": "sequenz",
            "DB_PASSWORD": "secret",
        })
