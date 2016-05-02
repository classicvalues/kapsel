# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

import os

from anaconda_project.commands.main import _parse_args_and_run_subcommand
from anaconda_project.commands.prepare import prepare_command, main
from anaconda_project.commands.prepare_with_mode import (UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                                                         UI_MODE_TEXT_ASSUME_YES_PRODUCTION, UI_MODE_TEXT_ASSUME_NO)
from anaconda_project.internal.test.tmpfile_utils import with_directory_contents
from anaconda_project.project_file import DEFAULT_PROJECT_FILENAME

from anaconda_project.test.project_utils import project_dir_disable_dedicated_env


class Args(object):
    def __init__(self, **kwargs):
        self.project = "."
        self.environment = 'default'
        self.mode = UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT
        for key in kwargs:
            setattr(self, key, kwargs[key])


def _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch):
    can_connect_args = dict()

    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        can_connect_args['host'] = host
        can_connect_args['port'] = port
        can_connect_args['timeout_seconds'] = timeout_seconds
        return True

    monkeypatch.setattr("anaconda_project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)

    return can_connect_args


def _test_prepare_command(monkeypatch, ui_mode):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)

    def prepare_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = prepare_command(dirname, ui_mode, conda_environment=None)
        assert can_connect_args['port'] == 6379
        assert result

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, prepare_redis_url)


def test_prepare_command_development(monkeypatch):
    _test_prepare_command(monkeypatch, UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT)


def test_prepare_command_production(monkeypatch):
    _test_prepare_command(monkeypatch, UI_MODE_TEXT_ASSUME_YES_PRODUCTION)


def test_prepare_command_assume_no(monkeypatch):
    _test_prepare_command(monkeypatch, UI_MODE_TEXT_ASSUME_NO)


def _monkeypatch_open_new_tab(monkeypatch):
    from tornado.ioloop import IOLoop

    http_results = {}

    def mock_open_new_tab(url):
        from anaconda_project.internal.test.http_utils import http_get_async, http_post_async
        from tornado import gen

        @gen.coroutine
        def do_http():
            http_results['get'] = yield http_get_async(url)
            http_results['post'] = yield http_post_async(url, body="")

        IOLoop.current().add_callback(do_http)

    monkeypatch.setattr('webbrowser.open_new_tab', mock_open_new_tab)

    return http_results


def test_main(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)
    _monkeypatch_open_new_tab(monkeypatch)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        main(Args(project=dirname, mode='browser'))

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "# Configure the project at " in out
    assert "" == err


def test_main_dirname_not_provided_use_pwd(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)
    _monkeypatch_open_new_tab(monkeypatch)

    def main_redis_url(dirname):
        from os.path import abspath as real_abspath

        def mock_abspath(path):
            if path == ".":
                return dirname
            else:
                return real_abspath(path)

        monkeypatch.setattr('os.path.abspath', mock_abspath)
        project_dir_disable_dedicated_env(dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--mode=browser'])
        assert code == 0

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "# Configure the project at " in out
    assert "" == err


def test_main_dirname_provided_use_it(monkeypatch, capsys):
    can_connect_args = _monkeypatch_can_connect_to_socket_to_succeed(monkeypatch)
    _monkeypatch_open_new_tab(monkeypatch)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        code = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--project', dirname, '--mode=browser'])
        assert code == 0

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    assert can_connect_args['port'] == 6379

    out, err = capsys.readouterr()
    assert "# Configure the project at " in out
    assert "" == err


def _monkeypatch_can_connect_to_socket_to_fail_to_find_redis(monkeypatch):
    def mock_can_connect_to_socket(host, port, timeout_seconds=0.5):
        if port == 6379:
            return False  # default Redis not there
        else:
            return True  # can't start a custom Redis here

    monkeypatch.setattr("anaconda_project.plugins.network_util.can_connect_to_socket", mock_can_connect_to_socket)


def test_main_fails_to_redis(monkeypatch, capsys):
    _monkeypatch_can_connect_to_socket_to_fail_to_find_redis(monkeypatch)
    _monkeypatch_open_new_tab(monkeypatch)

    from anaconda_project.commands.prepare_with_mode import prepare_with_ui_mode_printing_errors as real_prepare

    def _mock_prepare_do_not_keep_going(project,
                                        environ=None,
                                        ui_mode=UI_MODE_TEXT_ASSUME_YES_DEVELOPMENT,
                                        extra_command_args=None):
        return real_prepare(project, environ, ui_mode=ui_mode, extra_command_args=extra_command_args)

    monkeypatch.setattr('anaconda_project.commands.prepare_with_mode.prepare_with_ui_mode_printing_errors',
                        _mock_prepare_do_not_keep_going)

    def main_redis_url(dirname):
        project_dir_disable_dedicated_env(dirname)
        code = main(Args(project=dirname))
        assert 1 == code

    with_directory_contents({DEFAULT_PROJECT_FILENAME: """
services:
  REDIS_URL: redis
"""}, main_redis_url)

    out, err = capsys.readouterr()
    assert "missing requirement" in err
    assert "All ports from 6380 to 6449 were in use" in err


def test_prepare_command_choose_environment(capsys, monkeypatch):
    def mock_conda_create(prefix, pkgs, channels):
        from anaconda_project.internal.makedirs import makedirs_ok_if_exists
        metadir = os.path.join(prefix, "conda-meta")
        makedirs_ok_if_exists(metadir)
        for p in pkgs:
            pkgmeta = os.path.join(metadir, "%s-0.1-pyNN.json" % p)
            open(pkgmeta, 'a').close()

    monkeypatch.setattr('anaconda_project.internal.conda_api.create', mock_conda_create)

    def check_prepare_choose_environment(dirname):
        wrong_envdir = os.path.join(dirname, "envs", "foo")
        envdir = os.path.join(dirname, "envs", "bar")
        result = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--project', dirname,
                                                 '--environment=bar'])
        assert result == 0

        assert os.path.isdir(envdir)
        assert not os.path.isdir(wrong_envdir)

        package_json = os.path.join(envdir, "conda-meta", "nonexistent_bar-0.1-pyNN.json")
        assert os.path.isfile(package_json)

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
environments:
  foo:
    dependencies:
        - nonexistent_foo
  bar:
    dependencies:
        - nonexistent_bar
"""}, check_prepare_choose_environment)

    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


def test_prepare_command_choose_environment_does_not_exist(capsys):
    def check_prepare_choose_environment_does_not_exist(dirname):
        project_dir_disable_dedicated_env(dirname)
        result = _parse_args_and_run_subcommand(['anaconda-project', 'prepare', '--project', dirname,
                                                 '--environment=nope'])
        assert result == 1

        expected_error = "Environment name 'nope' is not in %s, these names were found: bar, foo" % os.path.join(
            dirname, DEFAULT_PROJECT_FILENAME)
        out, err = capsys.readouterr()
        assert out == ""
        assert expected_error in err

    with_directory_contents(
        {DEFAULT_PROJECT_FILENAME: """
environments:
  foo:
    dependencies:
        - nonexistent_foo
  bar:
    dependencies:
        - nonexistent_bar
"""}, check_prepare_choose_environment_does_not_exist)
