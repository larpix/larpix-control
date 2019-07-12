import warnings
warnings.simplefilter('default', DeprecationWarning)

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

    def __init__(self, enabled=False, *args, **kwargs):
        '''
        Create new logger instance.

        '''
        self._enabled = enabled
        self._open = False

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
        return self._enabled

    def enable(self):
        '''
        Enable logger

        '''
        self._enabled = True

    def disable(self):
        '''
        Disable logger

        .. note:: This flushes any data in the buffer before disabling

        '''
        if self._enabled:
            self.flush()
        self._enabled = False

    def is_open(self):
        '''
        Returns the value of the internal state "open/closed" (``True``
        if open).

        .. deprecated:: 2.4.0
           ``open``, ``close``, and ``is_open`` are deprecated and will
           be removed in the next major release of larpix-control.

        '''
        warnings.warn('open/close/is_open are deprecated and will be removed '
            'in the next major release of larpix-control.',
            DeprecationWarning, 2)
        return self._open

    def open(self, enable=True):
        '''
        Change internal state to "open" (meaningless), and if
        ``enable``, enable this logger (meaningful).

        :param enable: whether to enable this logger

        .. deprecated:: 2.4.0
           ``open``, ``close``, and ``is_open`` are deprecated and will
           be removed in the next major release of larpix-control.

        '''
        warnings.warn('open/close/is_open are deprecated and will be removed '
            'in the next major release of larpix-control.',
            DeprecationWarning, 2)
        if enable:
            self.enable()
        self._open = True
        return


    def close(self):
        '''
        Change internal state to "closed" (meaningless) and disable this
        logger (meaningful).

        .. deprecated:: 2.4.0
           ``open``, ``close``, and ``is_open`` are deprecated and will
           be removed in the next major release of larpix-control.

        '''
        warnings.warn('open/close/is_open are deprecated and will be removed '
            'in the next major release of larpix-control.',
            DeprecationWarning, 2)
        self._open = False
        self.disable()

    def flush(self):
        '''
        Flushes any held data from memory to the destination

        '''
        pass
