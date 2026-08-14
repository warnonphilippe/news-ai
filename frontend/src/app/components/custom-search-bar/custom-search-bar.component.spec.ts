import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CustomSearchBarComponent } from './custom-search-bar.component';

describe('CustomSearchBarComponent', () => {
  let fixture: ComponentFixture<CustomSearchBarComponent>;
  let component: CustomSearchBarComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CustomSearchBarComponent],
    }).compileComponents();
    fixture = TestBed.createComponent(CustomSearchBarComponent);
    component = fixture.componentInstance;
    // Pas de detectChanges() ici : certains tests doivent positionner un
    // @Input() AVANT le tout premier cycle pour que le binding [disabled]
    // couple a [(ngModel)] se reflete des la premiere passe (comportement
    // documente d'Angular avec les formulaires template-driven).
  });

  describe('submit() logic', () => {
    it('emits the trimmed query on valid submit', () => {
      const emitSpy = jest.spyOn(component.search, 'emit');
      component.query = '  RAG avec pgvector  ';
      component.submit();
      expect(emitSpy).toHaveBeenCalledWith('RAG avec pgvector');
    });

    it('emits an empty string for an empty query (= recherche du jour)', () => {
      const emitSpy = jest.spyOn(component.search, 'emit');
      component.query = '';
      component.submit();
      expect(emitSpy).toHaveBeenCalledWith('');
    });

    it('emits an empty string for a whitespace-only query', () => {
      const emitSpy = jest.spyOn(component.search, 'emit');
      component.query = '   ';
      component.submit();
      expect(emitSpy).toHaveBeenCalledWith('');
    });

    it('does not emit while pending, even with a valid query', () => {
      const emitSpy = jest.spyOn(component.search, 'emit');
      component.pending = true;
      component.query = 'valid query';
      component.submit();
      expect(emitSpy).not.toHaveBeenCalled();
    });
  });

  describe('label', () => {
    it('offers the daily search when the field is empty', () => {
      expect(component.label).toBe('Rechercher aujourd’hui');
    });

    it('offers a custom search once a criterion is typed', () => {
      component.query = 'RAG';
      expect(component.label).toBe('Rechercher');
    });

    it('shows the pending label whatever the field contains', () => {
      component.pending = true;
      component.query = 'RAG';
      expect(component.label).toBe('Recherche…');
    });
  });

  describe('template', () => {
    it('keeps the submit button enabled with an empty query', () => {
      fixture.detectChanges(); // query par defaut : ''
      const button: HTMLButtonElement = fixture.nativeElement.querySelector('button[type="submit"]');
      expect(button.disabled).toBe(false);
      expect(button.textContent).toContain('Rechercher aujourd’hui');
    });

    it('keeps the submit button enabled once a query is set', () => {
      fixture.detectChanges();
      component.query = 'test';
      fixture.detectChanges();

      const button: HTMLButtonElement = fixture.nativeElement.querySelector('button[type="submit"]');
      expect(button.disabled).toBe(false);
    });

    it('disables the input and shows a pending label while pending', async () => {
      // Le binding [disabled] est sur le MEME element que [(ngModel)] :
      // NgControl applique son propre etat "disabled" (issu du FormControl
      // sous-jacent) lors de sa propre verification, qui ne se stabilise
      // qu'apres plusieurs passes + un flush des microtasks de NgControl.
      // Verifie en conditions reelles (vrai clic souris dans un navigateur) :
      // le comportement est correct des qu'une interaction utilisateur reelle
      // declenche le cycle complet de detection de changements d'Angular
      // (zone.js), qui ne se limite jamais a une seule passe isolee comme un
      // detectChanges() manuel unique.
      fixture.detectChanges();
      component.pending = true;
      fixture.detectChanges();
      fixture.detectChanges();
      await fixture.whenStable();

      const input: HTMLInputElement = fixture.nativeElement.querySelector('input');
      const button: HTMLButtonElement = fixture.nativeElement.querySelector('button[type="submit"]');
      expect(input.disabled).toBe(true);
      expect(button.textContent).toContain('Recherche…');
    });

    it('submitting the form calls submit()', () => {
      fixture.detectChanges();
      const submitSpy = jest.spyOn(component, 'submit');
      const form: HTMLFormElement = fixture.nativeElement.querySelector('form');
      form.dispatchEvent(new Event('submit'));
      expect(submitSpy).toHaveBeenCalled();
    });
  });
});
