
class ExperimentInterface(object):
    """ Base interface for feature flag objects. """

    def variant(self, **args):
        """ Determine which variant, if any, of this experiment is active.

        :param baseplate.features.User user: The user you want to run the
            experiment on.
        :param baseplate.features.Content content: The content for this
            request. Can be either a subreddit, link, or comment.
        :param list url_flags:  Flags specified in the "features" parameter of
            the request url.  These can be used to force this function to
            return a specific variant.
        :rtype string:
        :returns: The name of the enabled variant as a string if any variant is
        enabled.  If no variant is enabled, return None.
        """
        raise NotImplementedError

    def should_log_bucketing(self):
        """Should this experiment log bucketing events to the event pipeline.
        """
        raise NotImplementedError
