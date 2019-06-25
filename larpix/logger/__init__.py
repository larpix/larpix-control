class Logger(object):
    '''
    Base class for larpix logger objects that explicity describes the necessary
    functions for a Logger implementation. Additional functions are not built
    into the larpix core.

    '''

    #: Flag to indicate packets were sent to ASICs
    WRITE = 0
    #: Flag to indicate packets were received from ASICs
    READ = 1

    def __init__(self, *args, **kwargs):
        '''
        Create new logger instance.

        '''
        pass

    def record(self, data, direction=0, *args, **kwargs):
        '''
        Log specified data.

        :param data: ``list`` of data to be written to log. Valid data types are specified by logger implementation. Raises a ``ValueError`` if datatype is invalid.
        :param direction: ``Logger.WRITE`` if packets were sent to
            ASICs, ``Logger.READ`` if packets
            were received from ASICs. (default: ``Logger.WRITE``)

        '''
        pass

    def is_enabled(self):
        '''
        Check if logger is enabled, i.e. actively recording data.
        All data passed into ``record()`` between an ``enable()`` and
        ``disable()`` command should be reflected in the log.

        '''
        pass

    def enable(self):
        '''
        Enable logger

        '''
        pass

    def disable(self):
        '''
        Disable logger

        '''
        pass

    def is_open(self):
        '''
        Check if logger is open. Opening a logger is only necessary if it is
        file-based. Regardless of the open/closed status, all data passed into
        ``record()`` between an ``enable()`` and ``disable()`` command should be
        reflected in the log.

        '''
        pass

    def open(self, enable=True):
        '''
        Open logger if it is not already.

        .. note:: You must close a logger after opening!

        :param enable: ``True`` if you want to enable the logger after opening

        '''

    def close(self):
        '''
        Close logger if it is not already

        '''
        pass

    def flush(self):
        '''
        Flushes any held data from memory to the destination

        '''
        pass
