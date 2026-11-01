/**
 * PNJ de la carte, sous le nom de leur repère dans Blender (NPC_*).
 * Dresseurs : `team` = [[n° Pokédex, niveau], …], `sprite` = sprite de combat (Showdown).
 * Habitants (`talk`) : répliques dites quand on leur parle.
 * Infirmière (`nurse`) et vendeur (`clerk`) : soins et boutique, aux deux comptoirs du Centre Pokémon.
 */
export const NPCS = {
  NPC_Nurse: { kind: 'nurse', name: 'Infirmière Joëlle' },
  NPC_Clerk: { kind: 'clerk', name: 'Vendeur' },
  NPC_TownKid: {
    kind: 'talk',
    name: 'Garçon',
    lines: [
      "Au Centre Pokémon, le comptoir de droite vend des Poké Balls et des Potions !",
      "Achète 10 Poké Balls d'un coup, et on t'offre une Honor Ball en cadeau !",
    ],
  },
  NPC_OldMan: {
    kind: 'talk',
    name: 'Vieil homme',
    lines: [
      "Bienvenue à Arabelle, jeune Dresseur.",
      "Si tes Pokémon sont fatigués, entre au Centre Pokémon. Les soins y sont gratuits !",
    ],
  },
  NPC_AccumulaLady: {
    kind: 'talk',
    name: 'Grand-mère',
    lines: [
      "Les bancs du jardin sont parfaits pour regarder passer les Dresseurs.",
      "Parfois, des gens viennent faire de grands discours sur l'estrade de la place…",
    ],
  },
  NPC_AccumulaMan: {
    kind: 'talk',
    name: 'Monsieur',
    lines: [
      "D'ici, sur le plateau, on voit toute la ville.",
      "Arabelle est bâtie sur une colline : il y a des escaliers partout !",
    ],
  },
  NPC_NuvemaLady: {
    kind: 'talk',
    name: 'Dame',
    lines: [
      "Renouet est une petite ville, mais le labo du Professeur y attire des Dresseurs de partout.",
      "Ta mère m'a dit que tu partais en voyage. Prends bien soin de tes Pokémon !",
    ],
  },
  NPC_NuvemaSailor: {
    kind: 'talk',
    name: 'Marin',
    lines: [
      "Ah, la brise du large ! Rien de tel pour se réveiller le matin.",
      "La Route 1 commence au nord de la ville. Au bout, tu trouveras Arabelle et son Centre Pokémon.",
    ],
  },
  NPC_BugCatcher: {
    kind: 'trainer',
    title: 'Scout',
    name: 'Théo',
    sprite: 'bugcatcher',
    team: [[540, 4], [543, 5]],
    reward: 80,
    intro: "Hé ! Tu marches sur mes insectes ! On règle ça en combat !",
    defeat: "Mes insectes ont besoin de repos…",
    after: "Les Pokémon Insecte deviennent très forts quand ils évoluent, tu verras !",
  },
  NPC_AceTrainer: {
    kind: 'trainer',
    title: 'Topdresseuse',
    name: 'Mélina',
    sprite: 'acetrainerf',
    team: [[519, 6], [546, 7]],
    reward: 420,
    intro: "Une Topdresseuse ne refuse jamais un défi. Montre-moi ce que tu vaux !",
    defeat: "Impressionnant… Tu as un vrai lien avec tes Pokémon.",
    after: "Les herbes hautes de la forêt cachent des Pokémon rares. Bonne chance !",
  },
  NPC_Youngster: {
    kind: 'trainer',
    title: 'Gamin',
    name: 'Hugo',
    sprite: 'youngster',
    team: [[504, 5], [506, 5], [509, 6]],
    reward: 120,
    intro: "Mon équipe est en haut du classement de mon quartier ! Combat !",
    defeat: "Pas possible… J'étais pourtant premier du quartier !",
    after: "Je vais m'entraîner encore plus dans les herbes hautes !",
  },
  NPC_Lass: {
    kind: 'trainer',
    title: 'Fillette',
    name: 'Lou',
    sprite: 'lass',
    team: [[531, 7]],
    reward: 140,
    intro: "Mon Nanméouïe est trop mignon, mais il sait se battre !",
    defeat: "Oh non, mon Nanméouïe…",
    after: "Les Pokémon aussi aiment qu'on les félicite après un combat.",
  },
};
