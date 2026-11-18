import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        RowLayout {
            spacing: 4
            Button {
                text: "+ Collection"
                font.pixelSize: 12
                Layout.fillWidth: true
                background: Rectangle {
                    color: parent.hovered ? theme.buttonHover : theme.buttonDefault
                    border.color: theme.borderButton
                    radius: 3
                }
                contentItem: Text {
                    text: parent.text
                    color: theme.buttonText
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: createCollectionDialog.show()
            }
            Button {
                text: "+ Request"
                font.pixelSize: 12
                Layout.fillWidth: true
                enabled: collectionsVM.rowCount() > 0
                background: Rectangle {
                    color: parent.enabled ? (parent.hovered ? theme.buttonHover : theme.buttonDefault) : theme.buttonDisabled
                    border.color: theme.borderButton
                    radius: 3
                }
                contentItem: Text {
                    text: parent.text
                    color: parent.enabled ? theme.buttonText : theme.buttonTextDisabled
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }

        ListView {
            id: collectionList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: collectionsVM
            clip: true
            focus: true

            delegate: ItemDelegate {
                id: delegateItem
                width: collectionList.width
                height: 32
                hoverEnabled: true

                background: Rectangle {
                    color: {
                        if (delegateItem.hovered) return theme.treeHover
                        if (collectionsVM.selected_index === index) return theme.accentSelected
                        return "transparent"
                    }
                    radius: 3
                }

                contentItem: RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 4
                    spacing: 4

                    Text {
                        text: model.name
                        color: theme.textPrimary
                        font.pixelSize: 12
                        font.bold: true
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Text {
                        text: "(" + model.requestCount + ")"
                        color: theme.textMuted
                        font.pixelSize: 11
                        visible: model.requestCount > 0
                    }
                }

                onClicked: collectionsVM.select_index(index)

                Menu {
                    id: contextMenu
                    MenuItem {
                        text: "Rename"
                        onTriggered: renameDialog.show()
                    }
                    MenuItem {
                        text: "Delete"
                        onTriggered: deleteDialog.show()
                    }
                }

                MouseArea {
                    anchors {
                        right: parent.right
                        top: parent.top
                        bottom: parent.bottom
                    }
                    width: 24
                    cursorShape: Qt.PointingHandCursor
                    visible: delegateItem.hovered
                    onClicked: contextMenu.popup()

                    Text {
                        anchors.centerIn: parent
                        text: "\u22EE"
                        color: theme.textMuted
                        font.pixelSize: 14
                    }
                }
            }
        }
    }

    Dialog {
        id: createCollectionDialog
        title: "New Collection"
        standardButtons: Dialog.Ok | Dialog.Cancel
        anchors.centerIn: parent
        modal: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 16

        function show() {
            collectionNameInput.text = ""
            open()
        }

        contentItem: ColumnLayout {
            spacing: 8
            width: 300

            Text {
                text: "Collection name:"
                color: theme.textPrimary
                font.pixelSize: 12
            }

            TextField {
                id: collectionNameInput
                Layout.fillWidth: true
                color: theme.textPrimary
                font.pixelSize: 12
                background: Rectangle {
                    color: theme.bgInput
                    border.color: theme.accentFocus
                    radius: 3
                }
            }
        }

        onOpened: collectionNameInput.forceActiveFocus()

        onAccepted: {
            var name = collectionNameInput.text.trim()
            if (name !== "") {
                collectionsVM.create_collection(name)
            }
        }
    }

    Dialog {
        id: renameDialog
        title: "Rename Collection"
        standardButtons: Dialog.Ok | Dialog.Cancel
        anchors.centerIn: parent
        modal: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 16

        function show() {
            renameInput.text = ""
            open()
        }

        contentItem: ColumnLayout {
            spacing: 8
            width: 300

            Text {
                text: "New name:"
                color: theme.textPrimary
                font.pixelSize: 12
            }

            TextField {
                id: renameInput
                Layout.fillWidth: true
                color: theme.textPrimary
                font.pixelSize: 12
                background: Rectangle {
                    color: theme.bgInput
                    border.color: theme.accentFocus
                    radius: 3
                }
            }
        }

        property int targetIndex: -1

        onOpened: renameInput.forceActiveFocus()

        onAccepted: {
            var name = renameInput.text.trim()
            if (name !== "" && targetIndex >= 0) {
                collectionsVM.rename_collection(targetIndex, name)
            }
        }
    }

    Dialog {
        id: deleteDialog
        title: "Delete Collection"
        standardButtons: Dialog.Yes | Dialog.No
        anchors.centerIn: parent
        modal: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 16

        function show() {
            open()
        }

        contentItem: Text {
            text: "Are you sure you want to delete this collection?"
            color: theme.textPrimary
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            width: 280
        }

        property int targetIndex: -1

        onAccepted: {
            if (targetIndex >= 0) {
                collectionsVM.delete_collection(targetIndex)
            }
        }
    }
}