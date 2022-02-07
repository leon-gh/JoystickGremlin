// -*- coding: utf-8; -*-
//
// Copyright (C) 2015 - 2021 Lionel Ott
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

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import gremlin.action_plugins


Item {
    id: _root

    implicitHeight: _button.height

    property InputStateCondition model

    Loader {
        id: _button

        active: _root.model.inputType == "button"

        // sourceComponent: ButtonComparator {
        //     comparator: _root.model.comparator
        // }
        
        sourceComponent: RowLayout {
            anchors.left: parent.left
            anchors.right: parent.right

            Label {
                text: "This input is"
            }

            ComboBox {
                model: ["Pressed", "Released"]
                onActivated: {
                    _root.model.comparator.isPressed = currentValue
                }
                Component.onCompleted: {
                    currentIndex = indexOfValue(_root.model.comparator.isPressed)
                }
            }
        }
    }
}