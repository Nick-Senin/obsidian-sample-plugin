import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting } from 'obsidian';
import { DAVClient, createAccount } from 'tsdav';
import { request as makeRequest } from "obsidian";


// Remember to rename these classes and interfaces!

interface MyPluginSettings {
	cal_dav_url:string; 
 	textField: string;
    passwordField: string;
    filePath: string;
    folderPath: string;
}

const DEFAULT_SETTINGS: MyPluginSettings = {
	cal_dav_url: '', 
   	textField: '', 
    passwordField: '', 
    filePath: '', 
    folderPath: '' 
}

export default class CreateNoteByEvent extends Plugin {
	settings: MyPluginSettings;


	async onload() {
		await this.loadSettings();
		console.log('Loaded settings:', this.settings); // Debug log to check settings

		const ribbonIconEl = this.addRibbonIcon('dice', 'Sample Plugin', (evt: MouseEvent) => {
			new Notice('Загружаю!');

			// Call the function when the ribbon icon is clicked
	        const boundDownloadTodayEvents = this.downloadTodayEvents.bind(this);
			boundDownloadTodayEvents();
		});

		ribbonIconEl.addClass('my-plugin-ribbon-class');
		console.log('log');
		this.addSettingTab(new SampleSettingTab(this.app, this));
	}

			async downloadTodayEvents() {
				try {
					console.log('Starting downloadTodayEvents');
					
					const calendarUrl = this.settings.cal_dav_url;
					const username = this.settings.textField;
					const password = this.settings.passwordField;

					// Encode credentials for Basic Auth
					const encodedCredentials = btoa(`${username}:${password}`);

					const response = await makeRequest({
						url: calendarUrl,
						method: 'PROPFIND',
						headers: {
							'Authorization': `Basic ${encodedCredentials}`,
							'Depth': '1',
							'Content-Type': 'application/xml; charset=utf-8'
						},
						body: `<?xml version="1.0" encoding="utf-8" ?>
							<propfind xmlns="DAV:">
								<prop>
								<calendar-data xmlns="urn:ietf:params:xml:ns:caldav"/>
								</prop>
							</propfind>`
					});

					// Parse the response and process the events
					// You'll need to implement the logic to parse the CalDAV response
					console.log('CalDAV response:', response);

					// Get today's date
					const today = new Date();
					today.setHours(0, 0, 0, 0);
					const tomorrow = new Date(today);
					tomorrow.setDate(tomorrow.getDate() + 1);

					// Filter events for today (implement this based on the parsed response)

					new Notice('Events downloaded successfully!');
				} catch (error) {
					console.error('Error downloading events:', error);
					new Notice('Failed to download events. Check console for details.');
				}
			}


	handleEventClick(event: any) {
		// TODO: Implement logic to handle event click, e.g., create or open a note
		console.log("Event clicked:", event);
	}
 
	onunload() {
	}

     async loadSettings() {
       this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
     }


	async saveSettings() {
		await this.saveData(this.settings);
	}



}

class SampleModal extends Modal {
	constructor(app: App) {
		super(app);
	}

	onOpen() {
		const {contentEl} = this;
		contentEl.setText('Woah!');
	}

	onClose() {
		const {contentEl} = this;
		contentEl.empty();
	}
}

class SampleSettingTab extends PluginSettingTab {
	plugin: CreateNoteByEvent;

	constructor(app: App, plugin: CreateNoteByEvent) {
		super(app, plugin);
		this.plugin = plugin;
	}

  display(): void {
        const {containerEl} = this;

        containerEl.empty();

        new Setting(containerEl)
            .setName('Url')
            .setDesc('A regular text field')
            .addText(text => text
                .setPlaceholder('Enter caldav url')
                .setValue(this.plugin.settings.cal_dav_url)
                .onChange(async (value) => {
                    this.plugin.settings.cal_dav_url = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Text field')
            .setDesc('A regular text field')
            .addText(text => text
                .setPlaceholder('Enter some text')
                .setValue(this.plugin.settings.textField)
                .onChange(async (value) => {
                    this.plugin.settings.textField = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Password field')
            .setDesc('A password field')
            .addText(text => text
                .setPlaceholder('Enter password')
                .setValue(this.plugin.settings.passwordField)
                .onChange(async (value) => {
                    this.plugin.settings.passwordField = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('File path')
            .setDesc('Select a file')
            .addText(text => text
                .setPlaceholder('Enter file path')
                .setValue(this.plugin.settings.filePath)
                .onChange(async (value) => {
                    this.plugin.settings.filePath = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Folder path')
            .setDesc('Select a folder')
            .addText(text => text
                .setPlaceholder('Enter folder path')
                .setValue(this.plugin.settings.folderPath)
                .onChange(async (value) => {
                    this.plugin.settings.folderPath = value;
                    await this.plugin.saveSettings();
                }));
	}
}
