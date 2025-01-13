import { ItemView, WorkspaceLeaf, Notice } from 'obsidian';
import CreateNoteByEvent from "main"

export class EventView extends ItemView {
    plugin: CreateNoteByEvent;
    currentDate: Date;

    constructor(leaf: WorkspaceLeaf, plugin: CreateNoteByEvent) {
        super(leaf);
        this.plugin = plugin;
        this.currentDate = new Date();
    }

    getViewType() {
        return "event-view";
    }

    getDisplayText() {
        return "Event View";
    }

    async onOpen() {
        await this.updateView();
    }

    async updateView() {
        const { contentEl } = this;
        contentEl.empty();

        const dateEl = contentEl.createEl('h2', { text: this.currentDate.toLocaleString('ru-RU', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) });

        const prevButton = contentEl.createEl('button', { text: 'Предыдущий день' });
        prevButton.onclick = () => this.changeDate(-1);

        const nextButton = contentEl.createEl('button', { text: 'Следующий день' });
        nextButton.onclick = () => this.changeDate(1);

        const events = await this.plugin.downloadTodayEvents(this.currentDate);


        const eventList = contentEl.createEl('ul');

        events?.forEach(event => {
            if (event) {
                const listItem = eventList.createEl('li');
                const startTime = event.event_date ? new Date(event.event_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A';
                listItem.setText(`${startTime} : ${event.event_title}`);

                listItem.addEventListener('click', async () => {
                   console.log("Event clicked:", event);
                   await this.plugin.createNoteFromTemplate(event);
                });   
            }
        });

    }

    async changeDate(days: number) {
        this.currentDate.setDate(this.currentDate.getDate() + days);
        await this.updateView();
    }
}