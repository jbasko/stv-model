# Pārnesamās balss vēlēšanu sistēmas skaitīšanas algoritma demonstrācija (programmētājiem)

Šis kods nav garantēti pareizs un ir paredzēts tikai informatīviem nolūkiem.

Tas demonstrē manu izpratni par pārnesamās balss vēlēšanu sistēmas (_Single Transferable Vote_, STV) skaitīšanas algoritmu,
kādu piedāvā Latvijā ieviest kustība _Bez partijām_.

Šis kods **netika** izmantots priekšlikuma izstrādē. Kļūdas šajā kodā ir manas kā programmētāja kļūdas.

## Zināmās problēmas

 * Testu gandrīz nav, tikai pavisam primitīvas lietas.
 * Svērtās balsis ar `float` zaudē precizitāti un var radīt nepareizus rezultātus salīdzināšanu dēļ.

## Kā izmēģināt


```python
from stv_model.model import Election

el = Election.from_votes(votes="""
    ab
    abc
    ace
    b
    b
    bca
    bcade
    cde
    ce
    ced
""", num_seats=2)
el.run_count()
```
