import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: mainWindow
    title: "AngryREST"
    width: 1400
    height: 900
    visible: true
    color: theme.bgPrimary

    menuBar: ToolBar {
        id: toolbar
        background: Rectangle {
            color: theme.bgSecondary
            border.color: theme.borderDefault
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 8

            Text {
                text: "Environment:"
                color: theme.textSecondary
                font.pixelSize: 12
            }

            ComboBox {
                id: envCombo
                Layout.minimumWidth: 180
                model: ["No Environment"]
                currentIndex: 0
                background: Rectangle {
                    color: theme.bgInput
                    border.color: theme.borderDefault
                    radius: 3
                }
                contentItem: Text {
                    text: envCombo.currentText
                    color: theme.textPrimary
                    font.pixelSize: 12
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Button {
                text: "Manage..."
                font.pixelSize: 12
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
            }

            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                color: theme.borderDefault
            }

            Button {
                text: "\u25B6 Run Collection"
                font.pixelSize: 12
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
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: toolbar.height + 2
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                id: collectionsPanel
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                color: theme.bgSecondary
                border.color: theme.borderDefault

                CollectionsPanel {
                    anchors.fill: parent
                    anchors.margins: 4
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: theme.bgPrimary

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 0

                    Text {
                        Layout.alignment: Qt.AlignCenter
                        text: "Select a request from the collection panel"
                        color: theme.textMuted
                        font.pixelSize: 13
                    }
                }
            }
        }

        Rectangle {
            id: statusBar
            Layout.fillWidth: true
            Layout.preferredHeight: 22
            color: theme.bgSecondary
            border.color: theme.borderDefault

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8

                Text {
                    text: "AngryREST v0.1.0"
                    color: theme.textStatusBar
                    font.pixelSize: 11
                }

                Item { Layout.fillWidth: true }

                Button {
                    text: "Logs"
                    flat: true
                    font.pixelSize: 11
                    contentItem: Text {
                        text: parent.text
                        color: theme.textStatusBar
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Item {}
                }
            }
        }
    }
}