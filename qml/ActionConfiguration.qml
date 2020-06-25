// -*- coding: utf-8; -*-
//
// Copyright (C) 2015 - 2019 Lionel Ott
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.


import QtQuick 2.14
import QtQuick.Controls 2.14
import QtQml.Models 2.14
import QtQuick.Window 2.14

import QtQuick.Controls.Universal 2.14

import gremlin.ui.profile 1.0


Item {
    property ActionConfigurationModel actionConfiguration
    id: idRoot

    anchors.left: parent.left
    anchors.right: parent.right
    anchors.rightMargin: 10
    height: _listView.childrenRect.height + _header.height + _headerBorder.height


    // +------------------------------------------------------------------------
    // | Header
    // +------------------------------------------------------------------------
    ActionConfigurationHeader {
        id: _header
        action: idRoot.actionConfiguration
    }
    BottomBorder {
        id: _headerBorder
        item: _header
    }

    // +------------------------------------------------------------------------
    // | Show every single library item associated with the input
    // +------------------------------------------------------------------------
    ListView {
        id: _listView

        anchors.top: _headerBorder.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: childrenRect.height
        spacing: 20

        model: actionConfiguration

        // Make it behave like a sensible scrolling container
        ScrollBar.vertical: ScrollBar {}
        flickableDirection: Flickable.VerticalFlick
        boundsBehavior: Flickable.StopAtBounds

        delegate: LibraryItem {
            action: idRoot.actionConfiguration
        }
    }

    Loader {
        anchors.top: _listView.bottom
        anchors.left: parent.left
        anchors.leftMargin: 10

        active: _listView.count == 0

        sourceComponent: ActionSelector {
            configuration: actionConfiguration
        }
    }

} // Item
