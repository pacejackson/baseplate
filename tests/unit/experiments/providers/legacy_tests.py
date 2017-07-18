
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import math
import time
import unittest

from baseplate._compat import iteritems, long, range
from baseplate.events import EventQueue
from baseplate.experiments import ExperimentsContextFactory
from baseplate.experiments.providers import experiment_from_config
from baseplate.experiments.providers.legacy import LegacyExperiment
from baseplate.features import Content, User, SessionContext
from baseplate.file_watcher import FileWatcher

from .... import mock


def get_users(num_users, logged_in=True):
    users = []
    for i in range(num_users):
        if logged_in:
            name = str(i)
        else:
            name = None
        users.append(User(
            name=name,
            id="t2_%s" % str(i),
            created=int(time.time()),
        ))
    return users


def generate_content(num_content, content_type):
    content = []

    if content_type == "subreddit":
        id_fmt = "t5_%s"
    elif content_type == "link":
        id_fmt = "t3_%s"
    elif content_type == "comment":
        id_fmt = "t1_%s"
    else:
        raise ValueError("Unknown content type: %s", content_type)

    for i in range(num_content):
        content.append(Content(id_fmt % i, content_type))

    return content


class TestLegacyExperiment(unittest.TestCase):

    def test_legacy_type_returns_legacy_experiment(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        }
        experiment_manager = experiment_from_config(cfg)
        self.assertTrue(isinstance(
            experiment_manager._experiment,
            LegacyExperiment,
        ))
        self.assertTrue(experiment_manager.should_log_bucketing())

    def test_calculate_bucket_value(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        }
        experiment = experiment_from_config(cfg)._experiment
        experiment.num_buckets = 1000
        self.assertEqual(experiment._calculate_bucket("t2_1"), long(236))
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "seed": "test-seed",
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        }
        seeded_experiment = experiment_from_config(cfg)._experiment
        self.assertNotEqual(seeded_experiment.seed, experiment.seed)
        self.assertIsNot(seeded_experiment.seed, None)
        seeded_experiment.num_buckets = 1000
        self.assertEqual(
            seeded_experiment._calculate_bucket("t2_1"),
            long(595),
        )

    def test_calculate_bucket(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        }
        experiment = experiment_from_config(cfg)._experiment

        # Give ourselves enough users that we can get some reasonable amount of
        # precision when checking amounts per bucket.
        num_users = experiment.num_buckets * 1000
        fullnames = []
        for i in range(num_users):
            fullnames.append("t2_%s" % str(i))

        counter = collections.Counter()
        for fullname in fullnames:
            bucket = experiment._calculate_bucket(fullname)
            counter[bucket] += 1
            # Ensure bucketing is deterministic.
            self.assertEqual(bucket, experiment._calculate_bucket(fullname))

        for bucket in range(experiment.num_buckets):
            # We want an even distribution across buckets.
            expected = num_users / experiment.num_buckets
            actual = counter[bucket]
            # Calculating the percentage difference instead of looking at the
            # raw difference scales better as we change num_users.
            percent_equal = float(actual) / expected
            self.assertAlmostEqual(percent_equal, 1.0, delta=.10,
                                   msg='bucket: %s' % bucket)

    def test_calculate_bucket_with_seed(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                },
                "seed": "itscoldintheoffice",
            }
        }
        experiment = experiment_from_config(cfg)._experiment

        # Give ourselves enough users that we can get some reasonable amount of
        # precision when checking amounts per bucket.
        num_users = experiment.num_buckets * 1000
        fullnames = []
        for i in range(num_users):
            fullnames.append("t2_%s" % str(i))

        counter = collections.Counter()
        bucketing_changed = False
        for fullname in fullnames:
            self.assertEqual(experiment.seed, "itscoldintheoffice")
            bucket1 = experiment._calculate_bucket(fullname)
            counter[bucket1] += 1
            # Ensure bucketing is deterministic.
            self.assertEqual(bucket1, experiment._calculate_bucket(fullname))

            current_seed = experiment.seed
            experiment.seed = "newstring"
            bucket2 = experiment._calculate_bucket(fullname)
            experiment.seed = current_seed
            # check that the bucketing changed at some point. Can't compare
            # bucket1 to bucket2 inline because sometimes the user will fall
            # into both buckets, and test will fail
            if bucket1 != bucket2:
                bucketing_changed = True

        self.assertTrue(bucketing_changed)

        for bucket in range(experiment.num_buckets):
            # We want an even distribution across buckets.
            expected = num_users / experiment.num_buckets
            actual = counter[bucket]
            # Calculating the percentage difference instead of looking at the
            # raw difference scales better as we change NUM_USERS.
            percent_equal = float(actual) / expected
            self.assertAlmostEqual(percent_equal, 1.0, delta=.10,
                                   msg='bucket: %s' % bucket)

    def test_choose_variant(self):
        control_only = experiment_from_config({
            "id": "1",
            "name": "control_only",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        })._experiment
        three_variants = experiment_from_config({
            "id": "1",
            "name": "three_variants",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    'remove_vote_counters': 5,
                    'control_1': 10,
                    'control_2': 5,
                }
            }
        })._experiment
        three_variants_more = experiment_from_config({
            "id": "1",
            "name": "three_variants_more",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    'remove_vote_counters': 15.6,
                    'control_1': 10,
                    'control_2': 20,
                }
            }
        })._experiment

        counters = collections.defaultdict(collections.Counter)
        for bucket in range(control_only.num_buckets):
            variant = control_only._choose_variant(bucket)
            if variant:
                counters[control_only.name][variant] += 1
            # Ensure variant-choosing is deterministic.
            self.assertEqual(variant, control_only._choose_variant(bucket))

            variant = three_variants._choose_variant(bucket)
            if variant:
                counters[three_variants.name][variant] += 1
            # Ensure variant-choosing is deterministic.
            self.assertEqual(variant, three_variants._choose_variant(bucket))

            previous_variant = variant
            variant = three_variants_more._choose_variant(bucket)
            if variant:
                counters[three_variants_more.name][variant] += 1
            # Ensure variant-choosing is deterministic.
            self.assertEqual(
                variant,
                three_variants_more._choose_variant(bucket)
            )
            # If previously we had a variant, we should still have the same one
            # now.
            if previous_variant:
                self.assertEqual(variant, previous_variant)

        for experiment in (control_only, three_variants, three_variants_more):
            for variant, percentage in iteritems(experiment.variants):
                count = counters[experiment.name][variant]
                scaled_percentage = float(count) / (experiment.num_buckets / 100)
                self.assertEqual(scaled_percentage, percentage)

        # Test boundary conditions around the maximum percentage allowed for
        # variants.
        fifty_fifty = experiment_from_config({
            "id": "1",
            "name": "fifty_fifty",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    'control_1': 50,
                    'control_2': 50,
                }
            }
        })._experiment
        almost_fifty_fifty = experiment_from_config({
            "id": "1",
            "name": "almost_fifty_fifty",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "variants": {
                    'control_1': 49,
                    'control_2': 51,
                }
            }
        })._experiment
        for bucket in range(fifty_fifty.num_buckets):
            for experiment in (fifty_fifty, almost_fifty_fifty):
                variant = experiment._choose_variant(bucket)
                counters[experiment.name][variant] += 1

        count = counters[fifty_fifty.name]['control_1']
        scaled_percentage = float(count) / (fifty_fifty.num_buckets / 100)
        self.assertEqual(scaled_percentage, 50)

        count = counters[fifty_fifty.name]['control_2']
        scaled_percentage = float(count) / (fifty_fifty.num_buckets / 100)
        self.assertEqual(scaled_percentage, 50)

        count = counters[almost_fifty_fifty.name]['control_1']
        scaled_percentage = float(count) / (almost_fifty_fifty.num_buckets / 100)
        self.assertEqual(scaled_percentage, 49)

        count = counters[almost_fifty_fifty.name]['control_2']
        scaled_percentage = float(count) / (almost_fifty_fifty.num_buckets / 100)
        self.assertEqual(scaled_percentage, 50)


class TestSimulatedLegacyExperiments(unittest.TestCase):

    def setUp(self):
        super(TestSimulatedLegacyExperiments, self).setUp()
        self.event_queue = mock.Mock(spec=EventQueue)
        self.mock_filewatcher = mock.Mock(spec=FileWatcher)
        self.factory = ExperimentsContextFactory("path", self.event_queue)
        self.factory._filewatcher = self.mock_filewatcher

    def _simulate_experiment(self, config, static_vars, target_var, targets):
        num_experiments = len(targets)
        counter = collections.Counter()
        self.mock_filewatcher.get_data.return_value = {config["name"]: config}
        for target in targets:
            session_vars = {target_var: target}
            session_vars.update(static_vars)
            user = session_vars.pop("user")
            session = SessionContext("1", user, url="https://www.reddit.com")
            session._url_properties = session_vars
            experiments = self.factory.make_object_for_context(None, None)
            variant = experiments.variant(config["name"], session)
            if variant:
                counter[variant] += 1

        # this test will still probabilistically fail, but we can mitigate
        # the likeliness of that happening
        error_bar_percent = 100. / math.sqrt(num_experiments)
        experiment = experiment_from_config(config)._experiment
        for variant, percent in iteritems(experiment.variants):
            # Our actual percentage should be within our expected percent
            # (expressed as a part of 100 rather than a fraction of 1)
            # +- 1%.
            measured_percent = (float(counter[variant]) / num_experiments) * 100
            self.assertAlmostEqual(
                measured_percent, percent, delta=error_bar_percent
            )

    def do_user_experiment_simulation(self, users, content, config):
        static_vars = {
            "content": content,
            "url_params": {},
            "subreddit": None,
            "subdomain": None,
        }
        return self._simulate_experiment(
            config=config,
            static_vars=static_vars,
            target_var="user",
            targets=users,
        )

    def do_page_experiment_simulation(self, user, pages, config):
        static_vars = {
            "user": user,
            "url_params": {},
            "subreddit": None,
            "subdomain": None,
        }
        return self._simulate_experiment(
            config=config,
            static_vars=static_vars,
            target_var="content",
            targets=pages,
        )

    def assert_no_user_experiment(self, users, content, config):
        self.mock_filewatcher.get_data.return_value = {config["name"]: config}
        for user in users:
            session = SessionContext("1", user)
            session._url_properties = {
                "content": content,
                "url_params": {},
                "subreddit": None,
                "subdomain": None,
            }
            experiments = self.factory.make_object_for_context(None, None)
            self.assertIs(experiments.variant(config["name"], session), None)

    def assert_no_page_experiment(self, user, pages, config):
        self.mock_filewatcher.get_data.return_value = {config["name"]: config}
        for page in pages:
            session = SessionContext("1", user)
            session._url_properties = {
                "content": page,
                "url_params": {},
                "subreddit": None,
                "subdomain": None,
            }
            experiments = self.factory.make_object_for_context(None, None)
            self.assertIs(experiments.variant(config["name"], session), None)

    def test_loggedin_experiment(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_in": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.do_user_experiment_simulation(
            users=get_users(2000),
            content=Content(None, None),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=False),
            content=Content(None, None),
            config=config,
        )

    def test_loggedin_experiment_explicit_enable(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "enabled": True,
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_in": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.do_user_experiment_simulation(
            users=get_users(2000),
            content=Content(None, None),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=False),
            content=Content(None, None),
            config=config,
        )

    def test_loggedin_experiment_explicit_disable(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "enabled": False,
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_in": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.assert_no_user_experiment(
            users=get_users(2000),
            content=Content(None, None),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=False),
            content=Content(None, None),
            config=config,
        )

    def test_loggedout_experiment(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_out": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.do_user_experiment_simulation(
            users=get_users(2000, logged_in=False),
            content=Content(None, None),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=True),
            content=Content(None, None),
            config=config,
        )

    def test_loggedout_experiment_missing_loids(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_out": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        users = get_users(2000, logged_in=False)
        for user in users:
            user.id = None
        self.assert_no_user_experiment(
            users=users,
            content=Content(None, None),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=True),
            content=Content(None, None),
            config=config,
        )

    def test_loggedout_experiment_explicit_enable(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_out": 100,
                },
            },
            "experiment": {
                "enabled": True,
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.do_user_experiment_simulation(
            users=get_users(2000, logged_in=False),
            content=Content(None, None),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=True),
            content=Content(None, None),
            config=config,
        )

    def test_loggedout_experiment_explicit_disable(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "enabled": False,
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_out": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=False),
            content=Content(None, None),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(2000, logged_in=True),
            content=Content(None, None),
            config=config,
        )

    def test_mixed_experiment(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_out": 100,
                    "percent_logged_in": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.do_user_experiment_simulation(
            users=get_users(1000) + get_users(1000, logged_in=False),
            content=Content(None, None),
            config=config,
        )

    def test_mixed_experiment_disable(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "enabled": False,
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {
                    "percent_logged_out": 100,
                    "percent_logged_in": 100,
                },
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.assert_no_user_experiment(
            users=get_users(1000) + get_users(1000, logged_in=False),
            content=Content(None, None),
            config=config,
        )

    def test_not_loggedin_or_loggedout(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "feature": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {},
            },
            "experiment": {
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.assert_no_user_experiment(
            users=get_users(1000) + get_users(1000, logged_in=False),
            content=Content(None, None),
            config=config,
        )

    def test_subreddit_experiment(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "page": True,
                "content_flags": {
                    "subreddit_only": True,
                },
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.do_page_experiment_simulation(
            user=get_users(1)[0],
            pages=generate_content(2000, "subreddit"),
            config=config,
        )
        self.assert_no_page_experiment(
            user=get_users(1)[0],
            pages=generate_content(2000, "link"),
            config=config,
        )
        self.assert_no_page_experiment(
            user=get_users(1)[0],
            pages=generate_content(2000, "comment"),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(1000) + get_users(1000, logged_in=False),
            content=Content(None, None),
            config=config,
        )

    def test_link_experiment(self):
        config = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "experiment": {
                "page": True,
                "content_flags": {
                    "link_only": True,
                },
                "variants": {
                    "larger": 5,
                    "smaller": 10,
                    "control_1": 10,
                    "control_2": 10,
                },
            },
        }
        self.do_page_experiment_simulation(
            user=get_users(1)[0],
            pages=generate_content(2000, "link"),
            config=config,
        )
        self.do_page_experiment_simulation(
            user=get_users(1)[0],
            pages=generate_content(2000, "comment"),
            config=config,
        )
        self.assert_no_page_experiment(
            user=get_users(1)[0],
            pages=generate_content(2000, "subreddit"),
            config=config,
        )
        self.assert_no_user_experiment(
            users=get_users(1000) + get_users(1000, logged_in=False),
            content=Content(None, None),
            config=config,
        )
