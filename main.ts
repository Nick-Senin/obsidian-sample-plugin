import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting, WorkspaceLeaf, TFile } from 'obsidian';
import { DAVClient, createAccount } from 'tsdav';
import { request as makeRequest } from "obsidian";
import { parseICS } from 'node-ical';
import {EventView} from 'EventView'; 

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
    eventView: EventView;
	settings: MyPluginSettings;

	async onload() {
		await this.loadSettings();
		console.log('Loaded settings:', this.settings); // Debug log to check settings

		this.registerView(
            "event-view",
            (leaf) => (this.eventView = new EventView(leaf, this))
        );

		this.addRibbonIcon('calendar-with-checkmark', 'Open Event View', (evt: MouseEvent) => {
            this.activateView();
        });

		const ribbonIconEl = this.addRibbonIcon('dice', 'Sample Plugin', (evt: MouseEvent) => {
			new Notice('Загружаю!');

			// Call the function when the ribbon icon is clicked
	        const today = new Date();
	        const boundDownloadTodayEvents = this.downloadTodayEvents.bind(this);

			const today_date = today;
			today_date.setDate(11); 

			boundDownloadTodayEvents(today_date);
		});

		ribbonIconEl.addClass('my-plugin-ribbon-class');
		console.log('log');
		this.addSettingTab(new SampleSettingTab(this.app, this));
	}

	async activateView() {
		const { workspace } = this.app;
		let leaf: WorkspaceLeaf | null = workspace.getLeavesOfType("event-view")[0];
		if (!leaf) {
			leaf = workspace.getRightLeaf(false);
			if (leaf) {
				await leaf.setViewState({ type: "event-view", active: true });
			}
		}
		if (leaf) workspace.revealLeaf(leaf);
	}

	async downloadTodayEvents(date: Date) {
		try {
			console.log('Starting downloadTodayEvents for date:', date.toISOString());
			
			const calendarUrl = this.settings.cal_dav_url;
			const username = this.settings.textField;
			const password = this.settings.passwordField;

			// Encode credentials for Basic Auth
			const encodedCredentials = btoa(`${username}:${password}`);

			// Format the date for the CalDAV query
			const formattedDate = date.toISOString().split('T')[0]; // YYYY-MM-DD format

			function formatDate(date: Date): string {
				const year = date.getFullYear();
				const month = (date.getMonth() + 1).toString().padStart(2, '0');
				const day = date.getDate().toString().padStart(2, '0');
				return `${year}${month}${day}`;
			}

			const formattedStartDate = formatDate(new Date(date));

			const response = await makeRequest({
				url: calendarUrl,
				method: 'REPORT',
				headers: {
					'Authorization': `Basic ${encodedCredentials}`,
					'Depth': '1',
					'Content-Type': 'application/xml; charset=utf-8'
				},
				body: `<?xml version="1.0" encoding="utf-8" ?>
					<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
						<d:prop>
							<d:getetag />
							<c:calendar-data />
						</d:prop>
						<c:filter>
							<c:comp-filter name="VCALENDAR">
								<c:comp-filter name="VEVENT">
									<c:time-range start="${formattedStartDate}T000000Z" end="${formattedStartDate}T235959Z"/>
								</c:comp-filter>
							</c:comp-filter>
						</c:filter>
					</c:calendar-query>`
			});

			console.log(response); 
			const events = parseICS(response);
			console.log('Events for', formattedDate, ':', Object.values(events)); 

			const processedEvents = Object.values(events).map(event => {
				if (event.type === 'VEVENT') {
					return {
						event_title: event.summary,
						event_date: event.start,
						event_org: typeof event.organizer === 'string' ? event.organizer : event.organizer?.params?.CN,
						event_participatns: Array.isArray(event.attendee) ? event.attendee.map(a => typeof a === 'object' ? (a.params?.cn || a.val) : a).join(', ') : (typeof event.attendee === 'object' ? (event.attendee.params?.cn || event.attendee.val) : event.attendee || ''),
						event_optional_participants: Array.isArray(event.attendee) ? event.attendee.filter(a => typeof a === 'object' && a.params?.role === 'OPT-PARTICIPANT').map(a => typeof a === 'object' ? (a.params?.cn || a.val) : a).join(', ') : '',
						event_location: event.location,
						event_link: event.url,
						event_description: event.description
					};
				}
				return null;
			}).filter(Boolean);

			console.log('Processed Events:', processedEvents);
			return processedEvents;

			new Notice(`Events for ${formattedDate} downloaded successfully!`);
		} catch (error) {
			console.error('Error downloading events:', error);
			new Notice('Не получилось загрузить события. Проверьте консоль.');
		}
	}
 
	onunload() {
	}

    async loadSettings() {
      this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    }

	async saveSettings() {
		await this.saveData(this.settings);
	}

	async createNoteFromTemplate(event: any) {
    const folderPath = this.settings.folderPath || '';
    const fileName = `${folderPath}/${event.event_title.replace(/[^a-zA-Z0-9а-яА-Я]/g, '_')}.md`;
    
    // Load the template from the specified file
    let template = '';
    const templatePath = this.settings.filePath+'.md';
    if (templatePath) {
        try {
			const templateFile = this.app.vault.getAbstractFileByPath(templatePath);

			if (templateFile && templateFile instanceof TFile) {
				template = await this.app.vault.read(templateFile as TFile);
			} else {
				console.error('Template file not found:', templatePath);
			}

        } catch (error) {
            console.error('Error reading template file:', error);
            new Notice('Error reading template file. Using default template.');
        }
    }

	console.log(template);
    // If no template was loaded, use a default template
    if (!template) {
        template = `# {event_title}

Date: {event_date}
Organizer: {event_org}
Participants: {event_participants}
Optional Participants: {event_optional_participants}
Location: {event_location}
Link: {event_link}

## Description
{event_description}
        `;
    }

    // Replace placeholders in the template with event data
    const fileContent = template
        .replace(/{event_title}/g, event.event_title)
        .replace(/{event_date}/g, event.event_date)
        .replace(/{event_org}/g, event.event_org || 'N/A')
        .replace(/{event_participants}/g, event.event_participatns || 'N/A')
        .replace(/{event_optional_participants}/g, event.event_optional_participants || 'N/A')
        .replace(/{event_location}/g, event.event_location || 'N/A')
        .replace(/{event_link}/g, event.event_link || 'N/A')
        .replace(/{event_description}/g, event.event_description || 'No description provided.');

    try {
        // Check if the folder exists, create only if it doesn't
        if (folderPath && !(await this.app.vault.adapter.exists(folderPath))) {
            await this.app.vault.createFolder(folderPath);
        }
        
        // Create the file in the specified folder
        const file = await this.app.vault.create(fileName, fileContent);
        new Notice(`Note created: ${fileName}`);

        // Try to open the file
        const leaf = this.app.workspace.getLeaf(false);
        if (leaf) {
            await leaf.openFile(file);
        } else {
            console.error('No available leaf to open the file');
            new Notice('Could not open the new note');
        }
    } catch (error) {
        console.error('Error creating note:', error);
        new Notice('Failed to create note. Check the console.');
    }
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
