from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional

class SingleLabelData(BaseModel):
    verbatim_text: str = Field(description="Verbatim text in a single data label.")

class LabelData(BaseModel):
    verbatim_all_text: List[SingleLabelData]
    verbatim_locality: str = Field(description="Locality as written on the label(s).")
    verbatim_collector: str = Field(description="Collector as written on the label(s).")
    verbatim_date: str = Field(description="Date as written on the label(s).")
    verbatim_coordinates: str = Field(description="Coordinates as written on the label(s).")
    verbatim_field_identifier: str = Field(description="Original identifier  as written on the label(s).")
    verbatim_taxon: str = Field(description="Species or other taxon name, including any author data and leg abbreviation, as written on the label(s).")
    verbatim_identified_by: str = Field(description="Name of the person who identified the sample as written on the label(s).")
    notes: str = Field(description="Other notes about the label data.")

if __name__ == '__main__':
    print("Testing")
    print(  LabelData.model_json_schema()   )
