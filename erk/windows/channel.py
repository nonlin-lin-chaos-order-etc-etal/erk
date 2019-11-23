
from datetime import datetime

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import QtCore

from erk.common import *
from erk.resources import *
from erk.strings import *
from erk.config import *
from erk.spelledit import *
from erk.format import *
import erk.events
import erk.input

from erk.dialogs import NewNickDialog

class Window(QMainWindow):

	def set_uptime(self,uptime):

		self.uptime = uptime

	def changeEvent(self,event):

		if event.type() == QEvent.WindowStateChange:
			if event.oldState() and Qt.WindowMinimized:
				if self.subwindow.isMinimized():
					self.channelChatDisplay.moveCursor(QTextCursor.End)
				if self.subwindow.isMaximized():
					self.channelChatDisplay.moveCursor(QTextCursor.End)
			elif event.oldState() == Qt.WindowNoState:
				self.channelChatDisplay.moveCursor(QTextCursor.End)
			elif self.windowState() == Qt.WindowMaximized:
				if self.subwindow.isMinimized():
					self.channelChatDisplay.moveCursor(QTextCursor.End)
				if self.subwindow.isMaximized():
					self.channelChatDisplay.moveCursor(QTextCursor.End)
		
		return QMainWindow.changeEvent(self, event)

	def closeEvent(self, event):

		if len(self.part_message)>0:
			self.client.sendLine("PART "+self.name+" "+self.part_message)
		else:
			self.client.sendLine("PART "+self.name)

		erk.events.erk_parted_channel(self.gui,self.client,self.name)

		if len(self.newlog)>0:
			if self.gui.save_logs:
				saveLog(self.client.network,self.name,self.newlog)

		if self.gui.title_from_active:
			self.gui.setWindowTitle(APPLICATION_NAME)

		if self.gui.save_channels:
			clean = []
			for e in self.client.kwargs["autojoin"]:
				if e[0]==self.name: continue
				clean.append(e)
			self.client.kwargs["autojoin"] = clean

		self.subwindow.close()
		event.accept()

	def handleUserInput(self):
		user_input = self.userTextInput.text()
		self.userTextInput.setText('')

		erk.input.channel_window_input(self.gui,self.client,self,user_input)

	def writeText(self,text):

		self.channelChatDisplay.append(text)
		self.channelChatDisplay.moveCursor(QTextCursor.End)

		self.channelChatDisplay.update()

	def rerenderText(self):
		self.reapplyStyles()
		self.channelChatDisplay.clear()
		for entry in self.log:
			mtype = entry[0]
			user = entry[1]
			message = entry[2]
			timestamp = entry[3]

			#line = render_message(self.gui.styles,mtype,user,message,timestamp)

			line = render_message(
				self.gui.styles,
				mtype,
				user,
				message,
				timestamp,
				self.gui.max_nick_size,
				self.gui.strip_html,
				self.gui.irc_color,
				self.gui.create_links,
				self.gui.show_timestamps,
				self.gui.show_timestamp_seconds,
				self.gui.show_timestamp_24hour_clock,
				self.gui.filter_profanity,
				self.gui.click_usernames,
			)

			self.channelChatDisplay.append(line)
		self.channelChatDisplay.moveCursor(QTextCursor.End)

	def reapplyStyles(self):

		text_color = get_style_attribute(self.gui.styles[BASE_STYLE_NAME],"color")
		if not text_color: text_color = "#000000"

		self.channelUserDisplay.setStyleSheet(self.gui.styles[BASE_STYLE_NAME])
		BASE_COLOR = self.channelUserDisplay.palette().color(QPalette.Base).name()
		DARKER_COLOR = color_variant(BASE_COLOR,-15)

		user_display_qss='''
			QListView::item::selected {
				border: 0px;
				background: !BASE!;
			}
			QListView::item:hover {
				background: !DARKER!;
			}
			QListView {
				show-decoration-selected: 0;
			}
			QListView::item {
				color: !TEXT_COLOR!;
			}
		'''
		user_display_qss = user_display_qss.replace('!DARKER!',DARKER_COLOR)
		user_display_qss = user_display_qss.replace('!BASE!',BASE_COLOR)
		user_display_qss = user_display_qss.replace('!TEXT_COLOR!',text_color)
		user_display_qss = user_display_qss + self.gui.styles[BASE_STYLE_NAME]

		self.channelUserDisplay.setStyleSheet(user_display_qss)

		self.channelChatDisplay.setStyleSheet(self.gui.styles[BASE_STYLE_NAME])
		self.userTextInput.setStyleSheet(self.gui.styles[BASE_STYLE_NAME])


	def writeLog(self,mtype,user,message):

		is_unseen = self.gui.window_activity_is_unseen(self)

		if mtype==CHAT_MESSAGE or mtype==ACTION_MESSAGE or mtype==NOTICE_MESSAGE:
			self.gui.window_activity(self)

		if self.gui.window_activity_is_unseen(self)!=is_unseen:
			# Window *just* got added to the unseen list
			if self.gui.mark_unread_messages:
				self.channelChatDisplay.insertHtml(UNSEEN_MESSAGES_MARKER)

		timestamp = datetime.timestamp(datetime.now())

		line = render_message(
			self.gui.styles,
			mtype,
			user,
			message,
			timestamp,
			self.gui.max_nick_size,
			self.gui.strip_html,
			self.gui.irc_color,
			self.gui.create_links,
			self.gui.show_timestamps,
			self.gui.show_timestamp_seconds,
			self.gui.show_timestamp_24hour_clock,
			self.gui.filter_profanity,
			self.gui.click_usernames,
		)

		self.channelChatDisplay.append(line)
		self.channelChatDisplay.moveCursor(QTextCursor.End)

		entry = [mtype,user,message,datetime.timestamp(datetime.now())]
		self.log.append(entry)
		self.newlog.append(entry)

	def writeTopic(self,topic):
		self.topic = topic
		if topic!='':
			self.setWindowTitle(" "+self.name+" - "+topic)
		else:
			self.setWindowTitle(" "+self.name)

	def refreshUserlist(self):
		self.writeUserlist(self.users)

	def writeUserlist(self,users):

		self.users = []
		self.operator = False
		self.voiced = False
		self.owner = False
		self.admin = False
		self.halfop = False

		self.channelUserDisplay.clear()

		# Sort the user list
		owners = []
		admins = []
		ops = []
		halfops = []
		voiced = []
		normal = []

		for u in users:
			if len(u)<1: continue
			self.users.append(u)
			p = u.split("!")
			if len(p)==2:
				nickname = p[0]
				hostmask = p[1]
			else:
				nickname = u
				hostmask = None

			if self.plain_user_lists:
				if '@' in nickname:
					ops.append(nickname)
					if nickname==self.client.nickname: self.operator = True
				elif '+' in nickname:
					voiced.append(nickname)
					if nickname==self.client.nickname: self.voiced = True
				elif '~' in nickname:
					owners.append(nickname)
					if nickname==self.client.nickname: self.owner = True
				elif '&' in nickname:
					admins.append(nickname)
					if nickname==self.client.nickname: self.admin = True
				elif '%' in nickname:
					halfops.append(nickname)
					if nickname==self.client.nickname: self.halfop = True
				else:
					normal.append(nickname)
			else:
				if '@' in nickname:
					ops.append(nickname.replace('@',''))
					if nickname.replace('@','')==self.client.nickname: self.operator = True
				elif '+' in nickname:
					voiced.append(nickname.replace('+',''))
					if nickname.replace('+','')==self.client.nickname: self.voiced = True
				elif '~' in nickname:
					owners.append(nickname.replace('~',''))
					if nickname.replace('~','')==self.client.nickname: self.owner = True
				elif '&' in nickname:
					admins.append(nickname.replace('&',''))
					if nickname.replace('&','')==self.client.nickname: self.admin = True
				elif '%' in nickname:
					halfops.append(nickname.replace('%',''))
					if nickname.replace('%','')==self.client.nickname: self.halfop = True
				else:
					normal.append(nickname)

		# Store a list of the nicks in this channel
		self.nicks = owners + admins + halfops + ops + voiced + normal

		# Alphabetize
		owners.sort()
		admins.sort()
		halfops.sort()
		ops.sort()
		voiced.sort()
		normal.sort()

		# Add owners
		for u in owners:
			ui = QListWidgetItem()
			if not self.plain_user_lists: ui.setIcon(QIcon(USERLIST_OWNER_ICON))
			ui.setText(u)
			self.channelUserDisplay.addItem(ui)

		# Add admins
		for u in admins:
			ui = QListWidgetItem()
			if not self.plain_user_lists: ui.setIcon(QIcon(USERLIST_ADMIN_ICON))
			ui.setText(u)
			self.channelUserDisplay.addItem(ui)

		# Add ops
		for u in ops:
			ui = QListWidgetItem()
			if not self.plain_user_lists: ui.setIcon(QIcon(USERLIST_OPERATOR_ICON))
			ui.setText(u)
			self.channelUserDisplay.addItem(ui)

		# Add halfops
		for u in halfops:
			ui = QListWidgetItem()
			if not self.plain_user_lists: ui.setIcon(QIcon(USERLIST_HALFOP_ICON))
			ui.setText(u)
			self.channelUserDisplay.addItem(ui)

		# Add voiced
		for u in voiced:
			ui = QListWidgetItem()
			if not self.plain_user_lists: ui.setIcon(QIcon(USERLIST_VOICED_ICON))
			ui.setText(u)
			self.channelUserDisplay.addItem(ui)

		# Add normal
		for u in normal:
			ui = QListWidgetItem()
			if not self.plain_user_lists: ui.setIcon(QIcon(USERLIST_NORMAL_ICON))
			ui.setText(u)
			self.channelUserDisplay.addItem(ui)

		self.channelUserDisplay.update()

	def _handleDoubleClick(self, item):
		item.setSelected(False)
		if self.gui.double_click_usernames:
			erk.events.user_double_click(self.gui,self.client,item.text())

	def linkClicked(self,url):
		if url.host():
			QDesktopServices.openUrl(url)
			self.channelChatDisplay.setSource(QUrl())
			self.channelChatDisplay.moveCursor(QTextCursor.End)
		else:
			link = url.toString()
			if self.gui.click_usernames:
				link = link.strip()
				erk.events.user_double_click(self.gui,self.client,link)
			self.channelChatDisplay.setSource(QUrl())
			self.channelChatDisplay.moveCursor(QTextCursor.End)

	def setKey(self,key):
		self.key = key
		changed = []
		for e in self.client.kwargs["autojoin"]:
			if e[0]==self.name:
				e[1] = key
			changed.append(e)
		self.client.kwargs["autojoin"] = changed

		if self.key=='':
			self.subwindow.setWindowIcon(QIcon(CHANNEL_WINDOW_ICON))
		else:
			self.subwindow.setWindowIcon(QIcon(LOCKED_CHANNEL_ICON))

	def setNick(self,nick):
		if self.gui.click_nick_change:
			self.nick.setText("<a style=\"color:inherit; text-decoration: none;\" href=\"!\"><b><small> "+nick+" </small></b></a>")
		else:
			self.nick.setText("<b><small> "+nick+" </small></b>")

	def onNickClick(self):
		self.nick.setText("<a style=\"color:inherit; text-decoration: none;\" href=\"!\"><b><small> "+self.client.nickname+" </small></b></a>")

	def offNickClick(self):
		self.nick.setText("<b><small> "+self.client.nickname+" </small></b>")

	def nickClicked(self,link):
		newnick = NewNickDialog(self.client.nickname,self)
		if newnick:
			self.client.setNick(newnick)

	def __init__(self,name,window_margin,subwindow,client,parent=None):
		super(Window, self).__init__(parent)

		self.name = name
		self.subwindow = subwindow
		self.client = client
		self.gui = parent

		self.uptime = 0

		self.is_channel = True
		self.is_console = False
		self.is_user = False

		self.part_message = ''

		# self.plain_user_lists = False
		self.plain_user_lists = self.gui.plain_user_lists

		self.users = []
		self.topic = ''

		self.nicks = []

		self.log = []
		self.newlog = []

		self.operator = False
		self.voiced = False
		self.owner = False
		self.admin = False
		self.halfop = False

		self.modeson = ''
		self.modesoff = ''
		self.key = ''

		if self.gui.save_channels:
			found = False
			for e in self.client.kwargs["autojoin"]:
				if e[0]==self.name: found = True
			if not found: self.client.kwargs["autojoin"].append([self.name,self.key])

		self.setWindowTitle(" "+self.name)
		self.setWindowIcon(QIcon(CHANNEL_WINDOW_ICON))

		self.channelChatDisplay = QTextBrowser(self)
		self.channelChatDisplay.setObjectName("channelChatDisplay")
		self.channelChatDisplay.setFocusPolicy(Qt.NoFocus)
		self.channelChatDisplay.anchorClicked.connect(self.linkClicked)

		self.channelUserDisplay = QListWidget(self)
		self.channelUserDisplay.setObjectName("channelUserDisplay")
		self.channelUserDisplay.setFocusPolicy(Qt.NoFocus)

		# Make sure that user status icons are just a little
		# bigger than the user entry text
		fm = QFontMetrics(self.channelChatDisplay.font())
		fheight = fm.height() + 2
		self.channelUserDisplay.setIconSize(QSize(fheight,fheight))

		self.channelUserDisplay.itemDoubleClicked.connect(self._handleDoubleClick)

		# User item background will darken slightly when hovered over
		self.channelUserDisplay.setStyleSheet(self.gui.styles[BASE_STYLE_NAME])

		text_color = get_style_attribute(self.gui.styles[BASE_STYLE_NAME],"color")
		if not text_color: text_color = "#000000"

		BASE_COLOR = self.channelUserDisplay.palette().color(QPalette.Base).name()
		DARKER_COLOR = color_variant(BASE_COLOR,-15)

		user_display_qss='''
			QListView::item::selected {
				border: 0px;
				background: !BASE!;
			}
			QListView::item:hover {
				background: !DARKER!;
			}
			QListView {
				show-decoration-selected: 0;
			}
			QListView::item {
				color: !TEXT_COLOR!;
			}
		'''
		user_display_qss = user_display_qss.replace('!DARKER!',DARKER_COLOR)
		user_display_qss = user_display_qss.replace('!BASE!',BASE_COLOR)
		user_display_qss = user_display_qss.replace('!TEXT_COLOR!',text_color)
		user_display_qss = user_display_qss + self.gui.styles[BASE_STYLE_NAME]

		self.channelUserDisplay.setStyleSheet(user_display_qss)

		self.ufont = self.channelUserDisplay.font()
		self.ufont.setBold(True)
		self.channelUserDisplay.setFont(self.ufont)

		self.userTextInput = SpellTextEdit(self)
		self.userTextInput.setObjectName("userTextInput")
		self.userTextInput.returnPressed.connect(self.handleUserInput)

		# Text input widget should only be one line
		fm = self.userTextInput.fontMetrics()
		self.userTextInput.setFixedHeight(fm.height()+9)
		self.userTextInput.setWordWrapMode(QTextOption.NoWrap)
		self.userTextInput.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.userTextInput.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

		self.userTextInput.changeLanguage(self.gui.spellCheckLanguage)

		self.channelChatDisplay.setStyleSheet(self.gui.styles[BASE_STYLE_NAME])
		self.userTextInput.setStyleSheet(self.gui.styles[BASE_STYLE_NAME])

		self.horizontalSplitter = QSplitter(Qt.Horizontal)
		self.horizontalSplitter.addWidget(self.channelChatDisplay)
		self.horizontalSplitter.addWidget(self.channelUserDisplay)
		
		# Set the initial splitter ratio
		ulwidth = (fm.width('X') + 2) + (fm.width('X')*18)
		mwidth = self.gui.initial_window_width-ulwidth
		self.horizontalSplitter.setSizes([mwidth,ulwidth])

		# Set the userlist to be no larger than 16 characters + icon
		self.channelUserDisplay.setMaximumWidth(ulwidth)

		if self.gui.click_nick_change:
			self.nick = QLabel("<a style=\"color:inherit; text-decoration: none;\" href=\"!\"><b><small> "+self.client.nickname+" </small></b></a>")
		else:
			self.nick = QLabel("<b><small> "+self.client.nickname+" </small></b>")
		self.nick.linkActivated.connect(self.nickClicked)

		entryLayout = QHBoxLayout()
		entryLayout.setSpacing(window_margin)
		entryLayout.setContentsMargins(window_margin,window_margin,window_margin,window_margin)
		entryLayout.addWidget(self.nick)
		entryLayout.addWidget(self.userTextInput)


		finalLayout = QVBoxLayout()
		finalLayout.setSpacing(window_margin)
		finalLayout.setContentsMargins(window_margin,window_margin,window_margin,window_margin)
		finalLayout.addWidget(self.horizontalSplitter)
		# finalLayout.addWidget(self.userTextInput)
		finalLayout.addLayout(entryLayout)

		interface = QWidget()
		interface.setLayout(finalLayout)
		self.setCentralWidget(interface)

		if not self.gui.show_nick_on_channel_windows: self.nick.hide()

		# Load logs
		if self.gui.load_logs:
			self.log = loadLog(self.client.network,self.name)
			if len(self.log)>0:
				if len(self.log)>self.gui.load_log_max:
					self.log = trimLog(self.log,self.gui.load_log_max)
				if self.gui.mark_end_of_loaded_logs: self.writeLog(HR_MESSAGE,'','')
				self.rerenderText()

