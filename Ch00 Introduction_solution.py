import random

def bevat_cijfers(tekst:str) -> bool:
    return any(char.isdigit() for char in tekst)

def maak_spionnennaam(voornaam, lievelingskleur):
    getal = random.randint(1, 99) # genereer een willekeurig geheel getal tussen 1 en 100
    # zet om naar string met twee posities en vul aan met nullen indien nodig
    getal = str(getal).zfill(2) # zfill zorgt ervoor dat het getal altijd twee cijfers heeft, bijvoorbeeld '01', '02', ..., '99'
    spionnennaam = voornaam[:3].upper() + str(getal) + lievelingskleur[-2:].upper()
    return spionnennaam

def main():
    vnaam = '0'
    while bevat_cijfers(vnaam):
        vnaam = input("Geef je voornaam in (zonder cijfers):")

    kleur = '0'
    while bevat_cijfers(kleur):
        kleur = input("Geef je lievelingskleur in (zonder cijfers):")
        
    spionnennaam = maak_spionnennaam(vnaam, kleur)
    print(f"Je spionnennaam is: {spionnennaam}")

if __name__ == "__main__":
    main()