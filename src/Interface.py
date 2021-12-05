import os
if os.environ.get('DISPLAY','') == '':
    print('no display found. Using :0.0')
    os.environ.__setitem__('DISPLAY', ':0.0')
import sys
import numpy
import time
import threading
from tkinter import *
from getpass import getuser
from tkinter import filedialog, messagebox
from tkinter.constants import CENTER, E, LEFT, N, NE, NW, RIGHT, SE, SW, W
from fluxclient.upnp import UpnpError
from fluxclient.upnp import UpnpDiscover
from fluxclient.toolpath import GCodeParser, FCodeV1FileWriter
from fluxclient.commands.misc import get_or_create_default_key

class callback:
	_device = None

	def fire(self, discoverInstance, device, **kw):
		deviceInfoText.setPrinterName(device.name)
		deviceInfoText.setPrinterIPAddress(device.ipaddr)
		discoverInstance.stop()
		self._device = device

class appText:
	_status = " "
	_fileName = " "
	_hotendTemp = "0"
	_printerName = " "
	_printPercent = "0.00"
	_uploadPercent = "0.00"
	_printerIPAddress = " "
	_connectionProgress = " "

	def getStatus(self):
		return self._status

	def getFileName(self):
		return self._fileName

	def getHotendTemp(self):
		return self._hotendTemp
	
	def getPrinterName(self):
		return self._printerName
	
	def getPrintPercent(self):
		return self._printPercent
	
	def getUploadPercent(self):
		return self._uploadPercent

	def getPrinterIPAddress(self):
		return self._printerIPAddress
	
	def getConnectionProgress(self):
		return self._connectionProgress
	
	def setStatus(self, status):
		self._status = status

	def setFileName(self, name):
		self._fileName = name
	
	def setHotendTemp(self, temp):
		self._hotendTemp = temp
	
	def setPrinterName(self, name):
		self._printerName = name
	
	def setPrintPercent(self, percent):
		self._printPercent = percent
	
	def setUploadPercent(self, percent):
		self._uploadPercent = percent
	
	def setPrinterIPAddress(self, address):
		self._printerIPAddress = address

	def setConnectionProgress(self, progress):
		self._connectionProgress = progress

class Connection:
	_device = None
	_printer = None
	_rsaKey = get_or_create_default_key("./connectionCertificate.pem")
	_connection = None

	def __init__(self, device):
		self._device = device

	def authorize(self, password):
		self._connection = self._device.manage_device(self._rsaKey)

		if self._connection.authorized:
			deviceInfoText.setConnectionProgress("Connecting...")
			self._printer = self._device.connect_robot(self._rsaKey)
		else:
			try:
				self._connection.authorize_with_password(password)
				self._connection.add_trust("my_public_key", self._rsaKey.public_key_pem.decode())
				deviceInfoText.setConnectionProgress("Connection authorized. Connecting...")
				self._printer = self._device.connect_robot(self._rsaKey)
			except UpnpError as e:
				deviceInfoText.setConnectionProgress("Authorization failed: %s" % e)
				raise
			
		if self._connection.connected:
			deviceInfoText.setConnectionProgress("Connection successfull!")
		else:
			deviceInfoText.setConnectionProgress("Connection failed")
			sys.exit()
		
		return True
	
	def listTrustedKeys(self):
		self._connection.list_trust()
	
	def close(self):
		self._connection.close()


class Delta:
	_task = None
	_printer = None
	_hardware = None
	_connection = None
	_filename = None
	_filepath = None
	
	def discover(self):
		c = callback()
		deviceInfoText.setConnectionProgress("Looking for printers on network...")
		UpnpDiscover().discover(c.fire, timeout = 120)
		self._hardware = c._device

		if(self._hardware != None):
			self._connection = Connection(self._hardware)
		else:
			self._connection = None

		return self._hardware
	
	def getConnection(self):
		if self._connection != None:
			return self._connection
		else:
			return False
	
	def getAndAssignPrinter(self):
		return self._connection._printer
	
	def getPrinter(self):
		return self._printer

	def getFile(self):
		self._filepath = filedialog.askopenfilename(initialdir = os.getcwd(), title = "Select File", filetypes = (("GCode", "*.gcode"), ("All Files", "*.*")))
		self._filename = os.path.basename(self._filepath)
		deviceInfoText.setFileName(self._filename)

	def convertAndUpload(self):
		_fcodeFilePath = None

		def uploadCallback(*args):
			deviceInfoText.setUploadPercent("{:.2f}".format((args[1] / args[2]) * 100))
			print(deviceInfoText.getUploadPercent())

		if(self._filename != None and len(self._filename) != 0):
			if(self._printer != None):
				_fcodeFilePath = os.getcwd() + "/" + os.path.splitext(self._filename)[0] + ".fcode"
				preview = ()
				metadata = {"AUTHOR": getuser(),"TITLE": self._filename,"CREATED_AT": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(time.time())),}
				parser = GCodeParser()
				processor = FCodeV1FileWriter(_fcodeFilePath, "EXTRUDER", metadata, preview)

				parser.set_processor(processor)
				parser.parse_from_file(self._filepath)
				processor.terminated()

				errors = processor.errors()
				if errors:
					for err in errors:
						sys.stderr.write(err.decode())
						sys.stderr.write("\n")
				
				self._printer.upload_file(_fcodeFilePath, process_callback = uploadCallback)
			else:
				messagebox.showinfo("Error", "No printer connected")
		else:
			messagebox.showinfo("Error", "You must select a GCode file first")

	def home(self):
		if(self._printer != None):
			self._task = self._printer.maintain()
			self._task.home()
			self._task.quit()
		else:
			messagebox.showinfo("Error", "No printer connected")

	def stopPrint(self):
		if(self._printer != None):
			self._printer.abort_play()
			self._printer.quit_play()
		else:
			messagebox.showinfo("Error", "No printer connected")

	def startPrint(self):
		if(self._printer != None):
			self._printer.start_play()
		else:
			messagebox.showinfo("Error", "No printer connected")

	def pausePrint(self):
		if(self._printer != None):
			self._printer.pause_play()
		else:
			messagebox.showinfo("Error", "No printer connected")

	def resumePrint(self):
		if(self._printer != None):
				self._printer.resume_play()
		else:
			messagebox.showinfo("Error", "No printer connected")

	def setTemp(self, temp):
		if(self._printer != None):
			if(len(temp) != 0):
				self._task = self._printer.maintain()
				try:
					self._task.set_extruder_temperature(int(0), float(temp))
				except:
					self._task.quit()
				
			else:
				messagebox.showinfo("Error", "You must specify a temperature first")
		else:
			messagebox.showinfo("Error", "No printer connected")


	def loadFillament(self):
		if(self._printer != None):
			return
		else:
			messagebox.showinfo("Error", "No printer connected")

	def unloadFillament(self):
		if(self._printer != None):
			return
		else:
			messagebox.showinfo("Error", "No printer connected")

	def run(self, device):
		device.discover()
		connection = device.getConnection()

		if connection:
			if connection.authorize("Flux"):
				self._printer = device.getAndAssignPrinter()
		else:
			deviceInfoText.setConnectionProgress("No devices discovered")
			self._printer = None
			exit()


def main():

	def updateText():
		if(device.getPrinter() != None):		
			printerStatus = device.getPrinter().report_play()
			print(printerStatus)
			
			if ("st_label" in printerStatus):
				deviceInfoText.setStatus(printerStatus["st_label"])

			if("prog" in printerStatus):
				deviceInfoText.setPrintPercent("{:.2f}".format(printerStatus["prog"] * 100))
			
			if("rt" in printerStatus and "tt" in printerStatus):
				temp = printerStatus["rt"]
				deviceInfoText.setHotendTemp(str(printerStatus["rt"]) + " / " + str(printerStatus["tt"]))

		
		fileNameEntry.config(state = NORMAL)
		fileNameEntry.delete(0, END)
		fileNameEntry.insert(0, deviceInfoText.getFileName())
		fileNameEntry.config(state = DISABLED)

		statusText.config(text = "Status: %s" % deviceInfoText.getStatus())
		hotendTemp.config(text = "TempC: %s" % deviceInfoText.getHotendTemp())
		printerNameText.config(text = "Name: %s" % deviceInfoText.getPrinterName())
		printPercentText.config(text = "Print: %s" % deviceInfoText.getPrintPercent() + "%")
		uploadPercentText.config(text = "Uploading: %s" % deviceInfoText.getUploadPercent() + "%")
		printerIPAddressText.config(text = "IP Address: %s" % deviceInfoText.getPrinterIPAddress())
		connectionProgressText.config(text = deviceInfoText.getConnectionProgress())

		root.after(500, func = updateText)

	root = Tk()
	root.configure(bg = "#263D42")
	root.title('FluxDelta Controller')
	root.geometry('{}x{}'.format(600, 600))

	root.grid_rowconfigure(0, weight = 5)
	root.grid_rowconfigure(1, weight = 1)
	root.grid_rowconfigure(2, weight = 1)
	root.grid_columnconfigure(0, weight = 1)

	printFrame = Frame(root, bg = "grey", width = 585, height = 190)
	controlFrame = Frame(root, bg = "grey", width = 585, height = 190)
	deviceInfoFrame = Frame(root, bg = "grey", width = 585, height = 190)

	printFrame.grid(row = 1, sticky = "nesw", padx = 15, pady = 10)
	controlFrame.grid(row = 2, sticky = "nesw", padx = 15, pady = 10)
	deviceInfoFrame.grid(row = 0, sticky = "nesw", padx = 15, pady = 10)

	printFrame.grid_rowconfigure(0, weight = 1)
	printFrame.grid_rowconfigure(1, weight = 10)
	printFrame.grid_columnconfigure(0, weight = 1)

	controlFrame.grid_rowconfigure(0, weight = 1)
	controlFrame.grid_rowconfigure(1, weight = 10)
	controlFrame.grid_columnconfigure(0, weight = 1)

	deviceInfoFrame.grid_rowconfigure(0, weight = 1)
	deviceInfoFrame.grid_rowconfigure(1, weight = 10)
	deviceInfoFrame.grid_columnconfigure(0, weight = 1)

	printFrameLabel = Label(printFrame, text = "Print", bg = "grey", font = ('Arial', 20))
	controlFrameLabel = Label(controlFrame, text = "Control", bg = "grey", font = ('Arial', 20))
	deviceInfoFrameLabel = Label(deviceInfoFrame, text = "Device Info", bg = "grey", font = ('Arial', 20))

	printFrameLabel.grid(row = 0, column = 0, sticky = "n")
	controlFrameLabel.grid(row = 0, column = 0, sticky = "n")
	deviceInfoFrameLabel.grid(row = 0, column = 0, sticky = "n")

	printSubFrame = Frame(printFrame, bg = "teal")
	controlSubFrame = Frame(controlFrame, bg = "teal")
	deviceInfoSubFrame = Frame(deviceInfoFrame, bg = "teal")

	printSubFrame.grid(row = 1, column = 0, sticky = "nesw", padx = 5, pady = 5)
	controlSubFrame.grid(row = 1, column = 0, sticky = "nesw", padx = 5, pady = 5)
	deviceInfoSubFrame.grid(row = 1, column = 0, sticky = "nesw", padx = 5, pady = 5)

	printSubFrame.grid_rowconfigure(0, weight = 1)
	printSubFrame.grid_rowconfigure(1, weight = 1)
	printSubFrame.grid_columnconfigure(0, weight = 1)
	printSubFrame.grid_columnconfigure(1, weight = 5)

	controlSubFrame.grid_rowconfigure(0, weight = 1)
	controlSubFrame.grid_rowconfigure(1, weight = 1)
	controlSubFrame.grid_rowconfigure(2, weight = 1)
	controlSubFrame.grid_columnconfigure(0, weight = 1)
	controlSubFrame.grid_columnconfigure(1, weight = 1)
	controlSubFrame.grid_columnconfigure(2, weight = 1)

	deviceInfoSubFrame.grid_rowconfigure(0, weight = 1)
	deviceInfoSubFrame.grid_rowconfigure(1, weight = 1)
	deviceInfoSubFrame.grid_columnconfigure(0, weight = 1)
	deviceInfoSubFrame.grid_columnconfigure(1, weight = 1)
	deviceInfoSubFrame.grid_propagate(False)

	convertBtn = Button(printSubFrame, text = "Convert and Upload", fg = "white", bg = "#263D42", command = device.convertAndUpload)
	selectFileBtn = Button(printSubFrame, text = "Select GCode File", fg = "white", bg = "#263D42", command = device.getFile)

	homeBtn = Button(controlSubFrame, text = "Home", fg = "white", bg = "#263D42", command = device.home)
	stopBtn = Button(controlSubFrame, text = "Stop Print", fg = "white", bg = "#263D42", command = device.stopPrint)
	startBtn = Button(controlSubFrame, text = "Start Print", fg = "white", bg = "#263D42", command = device.startPrint)
	pauseBtn = Button(controlSubFrame, text = "Pause Print", fg = "white", bg = "#263D42", command = device.pausePrint)
	resumeBtn = Button(controlSubFrame, text = "Resume Print", fg = "white", bg = "#263D42", command = device.resumePrint)
	setTempBtn = Button(controlSubFrame, text = "Set Temp", fg = "white", bg = "#263D42", command = lambda: device.setTemp(tempEntry.get()))
	loadFillamentBtn = Button(controlSubFrame, text = "Load Fillament", fg = "white", bg = "#263D42", command = device.loadFillament)
	unloadFillamentBtn = Button(controlSubFrame, text = "Unload Fillament", fg = "white", bg = "#263D42", command = device.unloadFillament)

	convertBtn.grid(row = 1, column = 0, sticky = "nesw", pady = 5, padx = 5)
	selectFileBtn.grid(row = 0, column = 0, sticky = "nesw", pady = 5, padx = 5)

	homeBtn.grid(row = 0, column = 0, sticky = "nesw", pady = 5, padx = 5)
	stopBtn.grid(row = 1, column = 0, sticky = "nesw", pady = 5, padx = 5)
	startBtn.grid(row = 2, column = 0, sticky = "nesw", pady = 5, padx = 5)
	pauseBtn.grid(row = 0, column = 1, sticky = "nesw", pady = 5, padx = 5)
	resumeBtn.grid(row = 1, column = 1, sticky = "nesw", pady = 5, padx = 5)
	setTempBtn.grid(row = 2, column = 1, sticky = "nesw", pady = 5, padx = 5)
	loadFillamentBtn.grid(row = 0, column = 2, sticky = "nesw", pady = 5, padx = 5)
	unloadFillamentBtn.grid(row = 1, column = 2, sticky = "nesw", pady = 5, padx = 5)

	tempEntry = Entry(controlSubFrame, bd = 5, width = 10, font = ('Arial', 20))
	fileNameEntry = Entry(printSubFrame, bd = 5, state = DISABLED, font = ('Arial', 20))

	tempEntry.grid(row = 2, column = 2, sticky = "nesw", padx = 5, pady = 5)
	fileNameEntry.grid(row = 0, column = 1, sticky = "nesw", padx = 5, pady = 5)

	printSubSubFrame = Frame(printSubFrame, bg = "orange")

	printSubSubFrame.grid(row = 1, column = 1, sticky = "nesw", padx = 5, pady = 5)

	printSubSubFrame.grid_rowconfigure(0, weight = 1)
	printSubSubFrame.grid_rowconfigure(1, weight = 1)
	printSubSubFrame.grid_rowconfigure(2, weight = 1)
	printSubSubFrame.grid_columnconfigure(0, weight = 1)

	statusText = Label(deviceInfoSubFrame, bg = "teal", font = ('Arial', 15))
	hotendTemp = Label(printSubSubFrame, bg = "orange", font = ('Arial', 15))
	printerNameText = Label(deviceInfoSubFrame, bg = "teal", font = ('Arial', 15))
	printPercentText = Label(printSubSubFrame, bg = "orange", font = ('Arial', 15))
	uploadPercentText = Label(printSubSubFrame, bg = "orange", font = ('Arial', 15))
	printerIPAddressText = Label(deviceInfoSubFrame, bg = "teal", font = ('Arial', 15))
	connectionProgressText = Label(deviceInfoSubFrame, bg = "teal", font = ('Arial', 15))

	statusText.grid(row = 1, column = 0, sticky = "nesw", padx = 5, pady = 5)
	hotendTemp.grid(row = 2, column = 0, sticky = "nesw", padx = 5, pady = 5)
	printerNameText.grid(row = 0, column = 1, sticky = "nesw", padx = 5, pady = 5)
	printPercentText.grid(row = 1, column = 0, sticky = "nesw", padx = 5, pady = 5)
	uploadPercentText.grid(row = 0, column = 0, sticky = "nesw", padx = 5, pady = 5)
	printerIPAddressText.grid(row = 1, column = 1, sticky = "nesw", padx = 5, pady = 5)
	connectionProgressText.grid(row = 0, column = 0, sticky = "nesw", padx = 5, pady = 5)
	
	threading.Thread(target = lambda: device.run(device)).start()
	root.after(0, func = updateText)
	root.mainloop()

if __name__ == '__main__':
	device = Delta()
	deviceInfoText = appText()
	main()