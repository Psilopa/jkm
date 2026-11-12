import json
# This is suss
# Suss values rank from +1 (probably ok) to 0 (unknown) to -1 (probably bad)
# Input: dictionary key:value_that_can_be_converted_to_string
from .mytyping import * # For typing

TESTING_JSON_FROM_AI = r"""{
  "verbatim_all_text": [
    {"verbatim_text": "Xanthorhoé designata Hfn."},
    {"verbatim_text": "SUOMI U. Nurmijärvi 17.6.1967 M. Koponen leg."},
    {"verbatim_text": "E714218"}
  ],
  "verbatim_locality": "U. Nurmijärvi",
  "verbatim_collector": "M. Koponen",
  "verbatim_date": "17.6.1967",
  "verbatim_coordinates": "",
  "verbatim_notebook_reference_code": "",
  "notebook_reference_code_label_properties": "",
  "verbatim_taxon": "Xanthorhoé designata Hfn.",
  "verbatim_identified_by": ""
}
"""

# output: dictionary with same keys, int = [-1...1] values
# Reference data:
#{} -> correctness_index
reference1 = [ ("verbatim_locality", "verbatim_collector", 0),
  ("U. Nurmijärvi", "M. Koponen", 1) ,
  ("U. Murmijärvi", "M. Koponen", -0.25) ,
  ("U. Murnijärvi", "M. Koponen", -0.5) ,
]

# Use a database here?
class refStorage():
    def __init__(self,data):
        self._fields = data[0][:-1]
        self.data = data[1:]
        print("self.fields", self.fields)
        tmpind = zip([x[:-1] for x in self.data],
                          [x[-1] for x in self.data])
        
        self.index = {k:v for (k,v) in tmpind}
    @property
    def fields(self): return self._fields
    def getcorrectness(self,x):
        return self.index.get(x,0.0) # Defaults to 0.0 (no opinion)
        
def simple_suss_o_meter(data, *args):
    sus = {k:0 for k in data.keys()}
    for ref in args:
        #Combo of fields to test
        totest = tuple(data[x] for x in ref.fields)
        print("test value = ", totest)
        # TODO: How should be assign suss values to individual fields in the combo is bad?
        val = ref.getcorrectness(totest)
        sus.update( {k:val for k in ref.fields} )
    return sus        
        
    
d = json.loads(TESTING_JSON_FROM_AI)       
ref1 = refStorage(reference1)
values = simple_suss_o_meter(d, ref1)

print("suss value = ",values )
