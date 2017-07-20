from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import collections
import time
import unittest

from baseplate._compat import long, range
from baseplate.experiments import User
from baseplate.experiments.providers import parse_experiment
from baseplate.file_watcher import FileWatcher, WatchedFileNotAvailableError

from .... import mock

logger = logging.getLogger(__name__)


THIRTY_DAYS_SEC = 60 * 60 * 24 * 30


class TestFeatureFlag(unittest.TestCase):

    def setUp(self):
        super(TestFeatureFlag, self).setUp()
        self.user = User(name="gary", id="t2_beef", created=int(time.time()))

    def _assert_fuzzy_percent_true(self, results, percent):
        stats = collections.Counter(results)
        total = sum(stats.values())
        # _roughly_ `percent` should have been `True`
        diff = abs((float(stats[True]) / total) - (percent / 100.0))
        self.assertTrue(diff < 0.1)

    def test_admin_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "admin": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["admin"],
        ), "active")

    def test_admin_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "admin": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=[],
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["beta"],
        ), "active")

    def test_employee_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "employee": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["employee"],
        ), "active")

    def test_employee_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "employee": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=[],
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["beta"],
        ), "active")

    def test_beta_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "beta": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["beta"],
        ), "active")

    def test_beta_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "beta": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=[],
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["admin"],
        ), "active")

    def test_gold_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "gold": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["gold"],
        ), "active")

    def test_gold_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "gold": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=[],
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["admin"],
        ), "active")

    def test_percent_loggedin(self):
        num_users = 2000
        users = []
        for i in range(num_users):
            users.append(User(
                name=str(i),
                id="t2_%s" % str(i),
                created=int(time.time()),
            ))

        def simulate_percent_loggedin(wanted_percent):
            cfg = {
                "id": "1",
                "name": "test_feature",
                "type": "feature_flag",
                "expires": int(time.time()) + THIRTY_DAYS_SEC,
                "experiment": {
                    "targeting": {
                        "logged_in": [True],
                    },
                    "variants": {
                        "active": wanted_percent,
                    },
                },
            }
            feature_flag = parse_experiment(cfg)
            return (
                feature_flag.variant(user_id=x.id, logged_in=x.logged_in) == "active"
                for x in users
            )

        self.assertFalse(any(simulate_percent_loggedin(0)))
        self.assertTrue(all(simulate_percent_loggedin(100)))
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(25), 25)
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(10), 10)
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(50), 50)
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(99), 99)

    def test_percent_loggedout(self):
        num_users = 2000
        users = []
        for i in range(num_users):
            users.append(User(
                name=None,
                id="t2_%s" % str(i),
                created=int(time.time()),
            ))

        def simulate_percent_loggedout(wanted_percent):
            cfg = {
                "id": "1",
                "name": "test_feature",
                "type": "feature_flag",
                "expires": int(time.time()) + THIRTY_DAYS_SEC,
                "experiment": {
                    "targeting": {
                        "logged_in": [False],
                    },
                    "variants": {
                        "active": wanted_percent,
                    },
                },
            }
            feature_flag = parse_experiment(cfg)
            return (
                feature_flag.variant(user_id=x.id, logged_in=x.logged_in) == "active"
                for x in users
            )

        self.assertFalse(any(simulate_percent_loggedout(0)))
        self.assertTrue(all(simulate_percent_loggedout(100)))
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(25), 25)
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(10), 10)
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(50), 50)
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(99), 99)

    def test_url_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "url_features": {
                        "test_state": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            url_features=["test_state"],
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            url_features=["x", "test_state"],
        ), "active")

    def test_url_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "url_features": {
                        "test_state": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            url_features=["x"],
        ), "active")

    def test_user_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_name": {
                        "Gary": "active",
                        "dave": "active",
                        "ALL_UPPERCASE": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_name="Gary",
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_name=self.user.name,
        ), "active")
        all_uppercase = User(
            name="ALL_UPPERCASE",
            id="t2_f00d",
            created=int(time.time())
        )
        self.assertEqual(feature_flag.variant(
            user_id=all_uppercase.id,
            logged_in=all_uppercase.logged_in,
            user_name=all_uppercase.name,
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=all_uppercase.id,
            logged_in=all_uppercase.logged_in,
            user_name=all_uppercase.name.lower(),
        ), "active")

    def test_user_not_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_name": {},
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_name=self.user.name,
        ), "active")
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_name": {
                        "dave": "active",
                        "joe": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_name=self.user.name,
        ), "active")

    def test_subreddit_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "subreddit": {
                        "WTF": "active",
                        "aww": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subreddit="WTF",
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subreddit="wtf",
        ), "active")

    def test_subreddit_not_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "subreddit": {},
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subreddit="wtf",
        ), "active")
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "subreddit": {
                        "wtfoobar": "active",
                        "aww": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subreddit="wtf",
        ), "active")

    def test_subdomain_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "subdomain": {
                        "beta": "active",
                        "www": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subdomain="beta",
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subdomain="BETA",
        ), "active")

    def test_subdomain_not_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "subdomain": {},
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subdomain="beta",
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subdomain="",
        ), "active")
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "subdomain": {
                        "www": "active",
                        "betanauts": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            subdomain="beta",
        ), "active")

    def test_multiple(self):
        # is_admin, globally off should still be False
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "global_override": None,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "admin": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["admin"],
        ), "active")

        # globally on but not admin should still be True
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "global_override": "active",
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "admin": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["admin"],
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")

        # no URL but admin should still be True
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "overrides": {
                    "user_groups": {
                        "admin": "active",
                    },
                    "url_features": {
                        "test_featurestate": "active",
                    },
                },
                "variants": {
                    "active": 0,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_groups=["admin"],
        ), "active")
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            url_features=["test_featurestate"],
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")

    def test_is_newer_than(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "newer_than": int(time.time()) - THIRTY_DAYS_SEC,
                "variants": {
                    "active": 100,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_created=int(time.time()),
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")

    def test_is_not_newer_than(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "feature_flag",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "newer_than": int(time.time()) + THIRTY_DAYS_SEC,
                "variants": {
                    "active": 100,
                },
            },
        }
        feature_flag = parse_experiment(cfg)
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
            user_created=int(time.time()),
        ), "active")
        self.assertNotEqual(feature_flag.variant(
            user_id=self.user.id,
            logged_in=self.user.logged_in,
        ), "active")
