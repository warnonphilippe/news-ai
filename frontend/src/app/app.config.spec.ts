import { appConfig } from './app.config';

describe('appConfig', () => {
  // Config purement declarative (cablage DI, aucune logique/branche propre) :
  // deja exercee implicitement par TestBed dans tous les autres fichiers de
  // specs qui injectent HttpClient. Ce test verifie juste sa forme.
  it('declares exactly the expected number of providers', () => {
    expect(appConfig.providers.length).toBe(2);
  });
});
