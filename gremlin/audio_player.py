# -*- coding: utf-8; -*-

#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from PySide6 import QtCore
from PySide6.QtCore import QUrl

from gremlin.common import SingletonDecorator
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


@SingletonDecorator
class AudioPlayer(QtCore.QObject):

    """Manages the playing of audio files."""

    def __init__(self) -> None:
        QtCore.QObject.__init__(self)
        self.player_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.player_output)

    def play(self, sound_filename: str, volume: int) -> None:
        """ volume: 0 = mute, >0 = volume level, max volume is 100 """

        if self.player.playbackState() != QMediaPlayer.StoppedState:
            self.player.stop()

        self.player.setSource(QUrl.fromLocalFile(sound_filename))
        self.player_output.setVolume(volume/100)
        self.player.play()
