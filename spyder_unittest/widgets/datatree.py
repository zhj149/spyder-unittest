# -*- coding: utf-8 -*-
#
# Copyright © 2017 Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
"""Model and view classes for storing and displaying test results."""

# Standard library imports
from collections import Counter

# Third party imports
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtGui import QBrush, QColor, QFont
from qtpy.QtWidgets import QTreeView
from spyder.config.base import get_translation

# Local imports
from spyder_unittest.backend.runnerbase import Category

try:
    _ = get_translation("unittest", dirname="spyder_unittest")
except KeyError as error:
    import gettext
    _ = gettext.gettext

COLORS = {
    Category.OK: QBrush(QColor("#C1FFBA")),
    Category.FAIL: QBrush(QColor("#FF0000")),
    Category.SKIP: QBrush(QColor("#C5C5C5")),
    Category.PENDING: QBrush(QColor("#C5C5C5"))
}

STATUS_COLUMN = 0
NAME_COLUMN = 1
MESSAGE_COLUMN = 2
TIME_COLUMN = 3

HEADERS = [_('Status'), _('Name'), _('Message'), _('Time (ms)')]

TOPLEVEL_ID = 2 ** 32 - 1


class TestDataView(QTreeView):
    """Tree widget displaying test results."""

    def __init__(self, parent=None):
        """Constructor."""
        QTreeView.__init__(self, parent)
        self.header().setDefaultAlignment(Qt.AlignCenter)
        self.setItemsExpandable(True)
        self.setSortingEnabled(False)

    def reset(self):
        """
        Reset internal state of the view and read all data afresh from model.

        This function is called whenever the model data changes drastically.
        It resizes the columns to fix their contents and makes the first column
        span the whole row in the second-level children, which display the test
        output.
        """
        QTreeView.reset(self)
        model = self.model()
        if model.hasChildren():
            for col in range(model.columnCount()):
                self.resizeColumnToContents(col)
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                for i in range(model.rowCount(index)):
                    self.setFirstColumnSpanned(i, index, True)

    # Not yet implemented ...
    # def item_activated(self, item):
    #     """Called if user clicks on item."""
    #     COL_POS = 0  # Position is not displayed but set as Qt.UserRole
    #     filename, line_no = item.data(COL_POS, Qt.UserRole)
    #     self.parent().edit_goto.emit(filename, line_no, '')


class TestDataModel(QAbstractItemModel):
    """
    Model class storing test results for display.

    Test results are stored as a list of TestResults in the property
    `self.testresults`. Every test is exposed as a child of the root node,
    with extra information as second-level nodes.

    As in every model, an iteem of data is identified by its index, which is
    a tuple (row, column, id). The id is TOPLEVEL_ID for top-level items.
    For level-2 items, the id is the index of the test in `self.testresults`.
    """

    def __init__(self, parent=None):
        """Constructor."""
        QAbstractItemModel.__init__(self, parent)
        self.testresults = []
        try:
            self.monospace_font = parent.window().editor.get_plugin_font()
        except AttributeError:  # If run standalone for testing
            self.monospace_font = QFont("Courier New")
            self.monospace_font.setPointSize(10)

    @property
    def testresults(self):
        """List of test results."""
        return self._testresults

    @testresults.setter
    def testresults(self, new_value):
        """Setter for test results."""
        self.beginResetModel()
        self._testresults = new_value
        self.endResetModel()

    def add_testresults(self, new_tests):
        """
        Add new test results to the model.

        Arguments
        ---------
        new_tests : list of TestResult
        """
        self.testresults += new_tests

    def index(self, row, column, parent=QModelIndex()):
        """
        Construct index to given item of data.

        If `parent` not valid, then the item of data is on the top level.
        """
        if not self.hasIndex(row, column, parent):  # check bounds etc.
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(row, column, TOPLEVEL_ID)
        else:
            testresult_index = parent.row()
            return self.createIndex(row, column, testresult_index)

    def data(self, index, role):
        """
        Return data in `role` for item of data that `index` points to.

        If `role` is `DisplayRole`, then return string to display.
        If `role` is `TooltipRole`, then return string for tool tip.
        If `role` is `FontRole`, then return monospace font for level-2 items.
        """
        if not index.isValid():
            return None
        row = index.row()
        column = index.column()
        id = index.internalId()
        if role == Qt.DisplayRole:
            if id != TOPLEVEL_ID:
                return self.testresults[id].extra_text[index.row()]
            elif column == STATUS_COLUMN:
                return self.testresults[row].status
            elif column == NAME_COLUMN:
                return self.testresults[row].name
            elif column == MESSAGE_COLUMN:
                return self.testresults[row].message
            elif column == TIME_COLUMN:
                time = self.testresults[row].time
                return str(time * 1e3) if time else ''
        elif role == Qt.ToolTipRole:
            if id == TOPLEVEL_ID and column == NAME_COLUMN:
                return '{0}.{1}'.format(self.testresults[row].module,
                                        self.testresults[row].name)
        elif role == Qt.FontRole:
            if id != TOPLEVEL_ID:
                return self.monospace_font
        elif role == Qt.BackgroundRole:
            if id == TOPLEVEL_ID:
                testresult = self.testresults[row]
                return COLORS[testresult.category]
        else:
            return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return data for specified header."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return HEADERS[section]
        else:
            return None

    def parent(self, index):
        """Return index to parent of item that `index` points to."""
        if not index.isValid():
            return QModelIndex()
        id = index.internalId()
        if id == TOPLEVEL_ID:
            return QModelIndex()
        else:
            return self.index(id, 0)

    def rowCount(self, parent=QModelIndex()):
        """Return number of rows underneath `parent`."""
        if not parent.isValid():
            return len(self.testresults)
        if parent.internalId() == TOPLEVEL_ID and parent.column() == 0:
            return len(self.testresults[parent.row()].extra_text)
        return 0

    def columnCount(self, parent=QModelIndex()):
        """Return number of rcolumns underneath `parent`."""
        if not parent.isValid():
            return len(HEADERS)
        else:
            return 1

    def summary(self):
        """Return summary for current results."""
        if not len(self.testresults):
            return _('No results to show.')
        counts = Counter(res.category for res in self.testresults)
        if counts[Category.FAIL] == 1:
            test_or_tests = _('test')
        else:
            test_or_tests = _('tests')
        failed_txt = '{} {} failed'.format(counts[Category.FAIL],
                                           test_or_tests)
        passed_txt = '{} passed'.format(counts[Category.OK])
        other_txt = '{} other'.format(counts[Category.SKIP])
        msg = '<b>{}, {}, {}</b>'.format(failed_txt, passed_txt, other_txt)
        return msg
