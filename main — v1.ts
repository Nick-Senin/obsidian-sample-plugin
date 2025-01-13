import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting } from 'obsidian';
import { DAVClient, createAccount } from 'tsdav';

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

			// Function to download events for today from CalDAV using tsdav
			const downloadTodayEvents = async () => {
				try {
					console.log('Starting downloadTodayEvents');
					
					const client = new DAVClient({
						serverUrl: "this.settings.cal_dav_url",
						credentials: {
							username: this.settings.textField,
							password: this.settings.passwordField
						},
						authMethod: 'Basic',
						defaultAccountType: 'caldav',
					});
					
					console.log('DAVClient created:', client);

					// Create account and fetch calendars
					console.log('Creating account...');

					const account = await createAccount({
						account: client,
					});
					
					console.log('Account created:', account);

					// Get today's date
					const today = new Date();
					today.setHours(0, 0, 0, 0);
					const tomorrow = new Date(today);
					tomorrow.setDate(tomorrow.getDate() + 1);

					// Fetch events for today ДОДЕЛАТЬ

					new Notice('Events downloaded successfully!');
				} catch (error) {
					console.error('Error downloading events:', error);
					new Notice('Failed to download events. Check console for details.');
				}
			};

			// Call the function when the ribbon icon is clicked
			downloadTodayEvents();
		});

		ribbonIconEl.addClass('my-plugin-ribbon-class');
		console.log('log');
		this.addSettingTab(new SampleSettingTab(this.app, this));
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
